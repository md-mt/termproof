//! Python 3 `re` dialect for `wait_for_regex`.
//!
//! `specs/002-builtin-steps/spec.md` FR-019 fixes the pattern dialect as
//! Python's `re`, "not PCRE and not the Rust `regex` crate", and tabulates
//! thirteen patterns executed against the oracle. The `regex` crate fails
//! three of them outright — it has no lookaround and no backreferences — so
//! the engine underneath is `fancy-regex`, which backtracks.
//!
//! That still leaves three rows where a backtracking engine with PCRE heritage
//! disagrees with Python *silently*, which is the worse failure: the pattern
//! compiles and quietly means something else.
//!
//! | Pattern | Python | `fancy-regex` unaided |
//! |---|---|---|
//! | `x\Z` on `"x\n"` | no match — `\Z` is absolute end-of-string | matches — PCRE's "before a final newline" |
//! | `\p{L}` | raises | matches any letter |
//! | `a{2,1}` | raises | reads it as `a{1,2}` |
//!
//! So patterns are translated before they reach the engine, and the two forms
//! Python refuses are refused here too. Nothing else is rewritten: every other
//! row of FR-019 is a row `fancy-regex` already gets right.

use fancy_regex::Regex;

/// A compiled Python-dialect pattern.
///
/// Owns the underlying `fancy-regex` engine and does not expose it. That is
/// deliberate: a third-party type in a public signature is only the same type
/// as the consumer's when cargo hands both sides one copy, which makes the
/// version requirement on that dependency a source-compatibility surface
/// rather than a private choice. Wrapping it moves the requirement back where
/// it belongs — see "Dependencies in the public API" in the crate docs (#177).
///
/// The surface here is what this crate needs plus what reading a match
/// requires; it is not a re-implementation of the engine. A caller that wants
/// the engine itself should depend on `fancy-regex` directly and pick its own
/// version — this crate deliberately does not re-export ours, because nothing
/// here hands out one of its types for the two to have to agree about.
///
/// ```
/// let re = termproof::pyregex::compile(r"(?<n>\d+)").unwrap();
/// let caps = re.captures("abc 42").unwrap().unwrap();
/// assert_eq!(caps.get(0).unwrap().as_str(), "42");
/// assert_eq!(caps.name("n").unwrap().as_str(), "42");
/// ```
pub struct PyRegex {
    inner: Regex,
    translated: String,
}

impl std::fmt::Debug for PyRegex {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        // Written out rather than derived, and deliberately does not format
        // `inner`. The engine's own `Debug` prints its parsed pattern, and that
        // rendering is not stable across its *patch* releases: `x\z` prints as
        // `x$` on `fancy-regex` 0.16.0 and 0.16.1 and as `x\z` on 0.16.2, all
        // three inside the range this crate declares. Deriving would put that
        // engine-version-dependent answer back into the public API — the same
        // leak `as_str` is written out to avoid, one trait over (#177).
        f.debug_struct("PyRegex")
            .field("translated", &self.translated)
            .finish_non_exhaustive()
    }
}

impl PyRegex {
    /// The translated pattern the engine was built from.
    ///
    /// This is the `fancy-regex` form, not the Python source: `translate`
    /// rewrites `\Z` and rejects what Python rejects, so the two differ
    /// wherever a rewrite applied.
    ///
    /// Kept as our own copy rather than read back from the engine. The engine's
    /// `as_str` is not stable across its own patch releases — `x\z` reads back
    /// as `x$` on `fancy-regex` 0.16.0 and as `x\z` on 0.16.2 — so forwarding
    /// to it would put an engine-version-dependent *answer* in this crate's
    /// public API, which is the same class of leak as putting its types there.
    /// Found by the `test at the declared dependency floors` CI step (#177).
    pub fn as_str(&self) -> &str {
        &self.translated
    }

    /// Whether the pattern matches anywhere in `haystack`.
    ///
    /// `Err` when the backtracking engine gives up on a pathological pattern.
    /// That is not a match and not a reason to end a run; callers here treat it
    /// as "no match" and carry on.
    pub fn is_match(&self, haystack: &str) -> Result<bool, String> {
        self.inner
            .is_match(haystack)
            .map_err(|e| one_line(&e.to_string()))
    }

    /// The capture groups of the leftmost match, or `None` when there is none.
    ///
    /// `Err` carries the same meaning as on [`is_match`](Self::is_match).
    pub fn captures<'h>(&self, haystack: &'h str) -> Result<Option<PyCaptures<'h>>, String> {
        // Read the groups out here rather than in a helper taking the engine's
        // own captures, so that `fancy_regex::Captures` is never *named*. It
        // gained a second generic parameter in 0.19, and a signature spelling
        // it would compile against one side of that change only — which is the
        // trap this whole wrapper exists to remove, and would reintroduce it
        // one layer down. Inference does not care (#177).
        let caps = match self.inner.captures(haystack) {
            Ok(Some(caps)) => caps,
            Ok(None) => return Ok(None),
            Err(e) => return Err(one_line(&e.to_string())),
        };
        let groups = (0..caps.len())
            .map(|i| {
                caps.get(i).map(|m| PyMatch {
                    text: m.as_str(),
                    start: m.start(),
                    end: m.end(),
                })
            })
            .collect();
        let names = self
            .inner
            .capture_names()
            .map(|n| n.map(str::to_string))
            .collect();
        Ok(Some(PyCaptures { groups, names }))
    }

    /// Every capture group's name in group order, `None` for the unnamed ones.
    ///
    /// Group 0 is the whole match and is never named, so the first item is
    /// always `None`.
    pub fn capture_names(&self) -> impl Iterator<Item = Option<&str>> + '_ {
        self.inner.capture_names()
    }
}

/// One matched span, borrowed from the haystack it was found in.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PyMatch<'h> {
    text: &'h str,
    start: usize,
    end: usize,
}

impl<'h> PyMatch<'h> {
    /// The matched text.
    pub fn as_str(&self) -> &'h str {
        self.text
    }

    /// Byte offset where the match starts in the haystack.
    pub fn start(&self) -> usize {
        self.start
    }

    /// Byte offset one past where the match ends.
    pub fn end(&self) -> usize {
        self.end
    }

    /// The matched span as a byte range.
    pub fn range(&self) -> std::ops::Range<usize> {
        self.start..self.end
    }
}

/// The capture groups of a single match.
///
/// Read eagerly at match time rather than borrowing the engine's own captures,
/// so nothing here is tied to the shape of a `fancy-regex` type. That is what
/// lets the requirement on that crate move without it being a break for
/// consumers (#177).
#[derive(Debug, Clone)]
pub struct PyCaptures<'h> {
    groups: Vec<Option<PyMatch<'h>>>,
    names: Vec<Option<String>>,
}

impl<'h> PyCaptures<'h> {
    /// Group `index`, or `None` when that group did not participate in the
    /// match. Group 0 is the whole match.
    pub fn get(&self, index: usize) -> Option<PyMatch<'h>> {
        self.groups.get(index).copied().flatten()
    }

    /// The group named `name`, or `None` when it did not participate or the
    /// pattern has no such group.
    pub fn name(&self, name: &str) -> Option<PyMatch<'h>> {
        let index = self.names.iter().position(|n| n.as_deref() == Some(name))?;
        self.get(index)
    }

    /// Every *named* group in group order, matched or not.
    ///
    /// Python's `groupdict()` carries an unmatched named group as `None` rather
    /// than dropping it, and so does this — which is what the step detail
    /// renders.
    pub fn named(&self) -> impl Iterator<Item = (&str, Option<PyMatch<'h>>)> + '_ {
        self.names
            .iter()
            .enumerate()
            .filter_map(|(i, n)| n.as_deref().map(|n| (n, self.get(i))))
    }

    /// The number of groups, counting group 0.
    pub fn len(&self) -> usize {
        self.groups.len()
    }

    /// Whether there are no groups at all.
    ///
    /// Never true for a match produced by [`PyRegex::captures`] — group 0
    /// always exists — but `len` without `is_empty` is a clippy warning and the
    /// answer is well defined.
    pub fn is_empty(&self) -> bool {
        self.groups.is_empty()
    }
}

/// Compile a pattern written in Python's `re` dialect.
///
/// The error is a single line by construction — constitution Principle VIII
/// forbids the multi-line ASCII-art parse errors the `regex` crate emits.
///
/// The wording is TermProof's own. Byte-parity with CPython's `re.error` text
/// is a separate question, open as 001-OQ-001 / 002-OQ-002 / 003-OQ-010.
pub fn compile(pattern: &str) -> Result<PyRegex, String> {
    let translated = translate(pattern)?;
    Regex::new(&translated)
        .map(|inner| PyRegex { inner, translated })
        .map_err(|e| one_line(&e.to_string()))
}

fn one_line(message: &str) -> String {
    message.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Rewrite a Python pattern into the equivalent `fancy-regex` pattern, or
/// reject it the way Python's parser would.
///
/// Positions in the messages count characters from the start of the pattern,
/// as Python's do.
fn translate(pattern: &str) -> Result<String, String> {
    let chars: Vec<char> = pattern.chars().collect();
    let mut out = String::with_capacity(pattern.len());
    let mut i = 0;
    let mut in_class = false;

    while i < chars.len() {
        match chars[i] {
            '\\' => {
                let Some(&next) = chars.get(i + 1) else {
                    return Err(format!("trailing backslash at position {i}"));
                };
                // Python's `re` has no `\p{...}`; it raises rather than
                // matching, so a recipe using one must not quietly start
                // meaning "any letter".
                if next == 'p' || next == 'P' {
                    return Err(format!("unsupported escape \\{next} at position {i}"));
                }
                // Python's `\Z` is the absolute end of the string. The engine's
                // `\Z` also matches before a trailing newline; `\z` does not.
                if next == 'Z' && !in_class {
                    out.push_str("\\z");
                } else {
                    out.push('\\');
                    out.push(next);
                }
                i += 2;
            }
            '[' if !in_class => {
                in_class = true;
                out.push('[');
                i += 1;
                if chars.get(i) == Some(&'^') {
                    out.push('^');
                    i += 1;
                }
                // A `]` immediately after `[` or `[^` is a literal in Python.
                // The engine needs it escaped to read it the same way.
                if chars.get(i) == Some(&']') {
                    out.push_str("\\]");
                    i += 1;
                }
            }
            ']' if in_class => {
                in_class = false;
                out.push(']');
                i += 1;
            }
            '{' if !in_class => match repetition_at(&chars, i) {
                Some(rep) => {
                    if let (Some(min), Some(max)) = (rep.min, rep.max) {
                        if min > max {
                            return Err(format!("repetition range is inverted at position {i}"));
                        }
                    }
                    // `{,n}` means `{0,n}` in Python and is a literal brace to
                    // the engine.
                    if rep.min.is_none() {
                        out.push_str("{0,");
                        out.push_str(&rep.max.unwrap_or_default().to_string());
                        out.push('}');
                    } else {
                        out.extend(chars[i..rep.end].iter());
                    }
                    i = rep.end;
                }
                // Not a quantifier, so a literal brace — which Python accepts
                // bare and the engine does not.
                None => {
                    out.push_str("\\{");
                    i += 1;
                }
            },
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    Ok(out)
}

/// A `{m,n}` quantifier, as far as Python's parser is concerned.
struct Repetition {
    /// One past the closing brace.
    end: usize,
    min: Option<u64>,
    max: Option<u64>,
}

/// Parse a repetition starting at `start` (which must index a `{`).
///
/// Returns `None` when the braces are not a quantifier at all — `a{`, `a{}`,
/// `a{,}` — which Python reads as literal text.
fn repetition_at(chars: &[char], start: usize) -> Option<Repetition> {
    let mut i = start + 1;
    let min_digits = digits_at(chars, &mut i);
    let comma = chars.get(i) == Some(&',');
    if comma {
        i += 1;
    }
    let max_digits = if comma {
        digits_at(chars, &mut i)
    } else {
        None
    };
    if chars.get(i) != Some(&'}') {
        return None;
    }
    if min_digits.is_none() && max_digits.is_none() {
        return None;
    }
    Some(Repetition {
        end: i + 1,
        min: min_digits,
        max: max_digits,
    })
}

/// Consume a run of ASCII digits, advancing `i`. A run too long for `u64` is
/// not a quantifier any engine will accept, so it reads as no digits at all.
fn digits_at(chars: &[char], i: &mut usize) -> Option<u64> {
    let start = *i;
    while chars.get(*i).is_some_and(|c| c.is_ascii_digit()) {
        *i += 1;
    }
    if *i == start {
        return None;
    }
    chars[start..*i].iter().collect::<String>().parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn is_match(pattern: &str, haystack: &str) -> bool {
        compile(pattern)
            .expect("pattern should compile")
            .is_match(haystack)
            .expect("match should not error")
    }

    #[test]
    fn translates_the_end_of_string_anchor() {
        assert_eq!(translate("x\\Z").unwrap(), "x\\z");
        assert!(!is_match("x\\Z", "x\n"));
        assert!(is_match("x\\Z", "x"));
    }

    #[test]
    fn leaves_other_escapes_alone() {
        assert_eq!(translate("\\A\\w+\\d\\\\").unwrap(), "\\A\\w+\\d\\\\");
    }

    #[test]
    fn rejects_unicode_property_escapes() {
        assert_eq!(
            compile("\\p{L}").unwrap_err(),
            "unsupported escape \\p at position 0"
        );
        assert_eq!(
            compile("ab\\P{L}").unwrap_err(),
            "unsupported escape \\P at position 2"
        );
    }

    /// An escaped backslash must not make the next character look escaped.
    #[test]
    fn a_doubled_backslash_does_not_swallow_the_next_escape() {
        assert!(compile("\\\\p").is_ok());
        assert!(compile("\\\\\\p{L}").is_err());
    }

    #[test]
    fn rejects_an_inverted_repetition_range() {
        assert_eq!(
            compile("a{2,1}").unwrap_err(),
            "repetition range is inverted at position 1"
        );
        assert!(compile("a{1,2}").is_ok());
        assert!(compile("a{2,}").is_ok());
        assert!(compile("a{2}").is_ok());
    }

    #[test]
    fn an_open_ended_lower_bound_means_zero() {
        assert_eq!(translate("a{,3}").unwrap(), "a{0,3}");
        assert!(is_match("^a{,3}$", "aa"));
    }

    #[test]
    fn a_brace_that_is_not_a_quantifier_is_a_literal() {
        assert!(is_match("a{", "a{"));
        assert!(is_match("a{}", "a{}"));
        assert!(is_match("a{,}", "a{,}"));
    }

    #[test]
    fn braces_inside_a_character_class_are_literal() {
        assert!(is_match("[{2,1}]", "{"));
        assert!(is_match("[{2,1}]", ","));
    }

    #[test]
    fn a_leading_close_bracket_is_a_class_member() {
        assert!(is_match("[]]", "]"));
        assert!(is_match("[^]]", "a"));
        assert!(!is_match("[^]]", "]"));
    }

    #[test]
    fn rejects_a_property_escape_inside_a_class() {
        assert!(compile("[\\p{L}]").is_err());
    }

    #[test]
    fn reports_a_trailing_backslash_rather_than_dropping_it() {
        assert_eq!(
            compile("ab\\").unwrap_err(),
            "trailing backslash at position 2"
        );
    }

    #[test]
    fn engine_errors_stay_on_one_line() {
        let err = compile("[bad").unwrap_err();
        assert!(!err.contains('\n'), "{err:?}");
    }

    #[test]
    fn counts_positions_in_characters_not_bytes() {
        assert_eq!(
            compile("é\\p{L}").unwrap_err(),
            "unsupported escape \\p at position 1"
        );
    }

    #[test]
    fn captures_reads_positional_groups_with_group_zero_first() {
        let re = compile(r"(\w+)@(\w+)").expect("compiles");
        let caps = re
            .captures("mail bob@host x")
            .expect("no engine error")
            .expect("matches");
        assert_eq!(caps.len(), 3);
        assert_eq!(caps.get(0).unwrap().as_str(), "bob@host");
        assert_eq!(caps.get(1).unwrap().as_str(), "bob");
        assert_eq!(caps.get(2).unwrap().as_str(), "host");
        assert!(caps.get(3).is_none());
    }

    #[test]
    fn a_match_carries_byte_offsets_into_the_haystack() {
        let re = compile(r"\d+").expect("compiles");
        let caps = re
            .captures("é 42")
            .expect("no engine error")
            .expect("matches");
        let m = caps.get(0).unwrap();
        // "é" is two bytes, then a space: the digits start at byte 3.
        assert_eq!(m.start(), 3);
        assert_eq!(m.end(), 5);
        assert_eq!(m.range(), 3..5);
        assert_eq!(m.as_str(), "42");
    }

    #[test]
    fn named_carries_an_unmatched_group_rather_than_dropping_it() {
        // Python's `groupdict()` reports `b` as None rather than omitting it,
        // and the step detail renders that, so `named` has to agree.
        let re = compile(r"(?<a>x)|(?<b>y)").expect("compiles");
        let caps = re.captures("x").expect("no engine error").expect("matches");
        let seen: Vec<(String, Option<String>)> = caps
            .named()
            .map(|(n, m)| (n.to_string(), m.map(|m| m.as_str().to_string())))
            .collect();
        assert_eq!(
            seen,
            vec![
                ("a".to_string(), Some("x".to_string())),
                ("b".to_string(), None),
            ]
        );
        assert_eq!(caps.name("a").unwrap().as_str(), "x");
        assert!(caps.name("b").is_none());
        assert!(caps.name("nonexistent").is_none());
    }

    #[test]
    fn a_pattern_that_does_not_match_is_none_not_an_error() {
        let re = compile("zzz").expect("compiles");
        assert!(re.captures("abc").expect("no engine error").is_none());
        assert!(!re.is_match("abc").expect("no engine error"));
    }

    #[test]
    fn debug_does_not_render_the_engine() {
        // `fancy-regex`'s own `Debug` prints its parsed pattern, and that
        // rendering moves across its patch releases (`x$` on 0.16.0 and 0.16.1,
        // `x\z` on 0.16.2). A derived `Debug` here would publish that. Pinning
        // the exact string is what makes re-deriving fail rather than pass with
        // a different answer on a different engine build.
        let re = compile("x\\Z").expect("compiles");
        assert_eq!(format!("{re:?}"), r#"PyRegex { translated: "x\\z", .. }"#);
    }

    #[test]
    fn as_str_reports_the_translated_pattern_not_the_python_source() {
        // `\Z` is rewritten to `\z`; that rewrite is why the two differ.
        let re = compile("x\\Z").expect("compiles");
        assert_eq!(re.as_str(), "x\\z");
    }
}
