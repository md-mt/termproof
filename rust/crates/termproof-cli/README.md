# termproof-cli

The `termproof` command line binary — evidence-first verification for TUI and
terminal applications. The Rust half of
[TermProof](https://github.com/md-mt/termproof).

> **Maturity: this port is in progress and is not at parity with the Python
> implementation.** The Python implementation at
> [`md-mt/termproof`](https://github.com/md-mt/termproof) is the shipped product
> and the behavioural oracle for TermProof; there is no parity gate for this
> port. Read
> [status and parity](https://github.com/md-mt/termproof/blob/main/rust/docs/status-and-parity.md)
> before depending on this binary.

## Install

**This crate is not published to crates.io** — its name is not being spent on
the registry while the binary is still moving, so `cargo install termproof-cli`
will not work. Install from a release tag, or build from a checkout:

```sh
cargo install --git https://github.com/md-mt/termproof termproof-cli
```

To pin a release, add `--tag rs-v<version>`. Rust releases are tagged `rs-v*`
in this repository; releases through `0.3.3` were cut before the two
implementations were consolidated and carry the older `v*` tags.

Or build from a checkout:

```sh
cargo build --manifest-path rust/Cargo.toml --release -p termproof-cli
```

The binary is named `termproof`. Prebuilt archives for tagged releases are
attached to the [GitHub releases](https://github.com/md-mt/termproof/releases).

## Use

```sh
termproof run <path>...
```

`run` discovers recipe files under the paths given, loads each one, plans
recipe × renderer, runs the steps against a real child on a pseudo-terminal,
and writes `result.json`, `report.md`, `raw_output.txt`, `screen.txt` and an
asciicast per run, plus `latest-report.md` — and a JUnit file when
`--xml-path` is given.

## What a run still cannot do

- **Only `execution: scripted` on a pty runs.** A recipe whose `command.pty` is
  false, or whose `execution` is anything else, is refused with a diagnostic
  naming the reason and a non-zero exit.
- **`--video`, `--diff`, `--update-baselines` and `--skip-unchanged` are parsed
  and ignored**, with a warning on stderr rather than silence.
- **Failures are not contained.** Turning recipe, step, plugin, process and PTY
  failures into structured results is not done yet.

## Licence

MIT — see [LICENSE](LICENSE).
