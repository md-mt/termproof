"""Tests for the shared screenshot deduper.

Mirrors ``rust/crates/termproof/src/evidence/dedup.rs``'s test module, so a
divergence between the two implementations of the rule shows up as a failing
test on one side rather than as two run directories that disagree about which
screens changed.

The two Python callers are covered where they live: ``test_collector.py`` for
:meth:`termproof.collector.EvidenceCollector.publish`, and
``test_evidence_config.py`` / ``test_step_attributed_screens.py`` for
:func:`termproof.evidence.render_artifacts`.
"""

from __future__ import annotations

import unittest

from termproof.attributed import (
    AttributedScreen,
    attributed_screen_from_ansi_text,
    attributed_screen_from_text,
)
from termproof.dedup import Deduper


def _text(value: str) -> AttributedScreen:
    return attributed_screen_from_text(value, columns=20, rows=2)


def _ansi(value: str) -> AttributedScreen:
    return attributed_screen_from_ansi_text(value, columns=20, rows=2)


class DeduperTest(unittest.TestCase):
    def test_the_first_screen_always_renders(self) -> None:
        deduper = Deduper()
        self.assertIsNone(deduper.check("first", _text("hello")))

    def test_an_unchanged_screen_reuses_the_previous(self) -> None:
        deduper = Deduper()
        deduper.check("first", _text("hello"))
        self.assertEqual("first", deduper.check("second", _text("hello")))

    def test_a_changed_screen_renders(self) -> None:
        deduper = Deduper()
        deduper.check("first", _text("hello"))
        self.assertIsNone(deduper.check("second", _text("goodbye")))

    def test_a_run_of_identical_screens_all_point_at_the_first(self) -> None:
        # Not at their immediate neighbour — a chain of "same as the one
        # before" is useless to a reader following it back.
        deduper = Deduper()
        deduper.check("first", _text("hello"))
        self.assertEqual("first", deduper.check("second", _text("hello")))
        self.assertEqual("first", deduper.check("third", _text("hello")))

    def test_same_text_different_colour_is_a_different_screenshot(self) -> None:
        # The reason this keys on attributes. A text-keyed cache collapses
        # these two and loses the frame where the selection moved.
        deduper = Deduper()
        deduper.check("red", _ansi("\x1b[31mhi"))
        self.assertIsNone(deduper.check("green", _ansi("\x1b[32mhi")))

    def test_identical_colour_and_text_still_dedupes(self) -> None:
        deduper = Deduper()
        deduper.check("red", _ansi("\x1b[31mhi"))
        self.assertEqual("red", deduper.check("red-again", _ansi("\x1b[31mhi")))

    def test_only_the_immediately_previous_screen_counts(self) -> None:
        # A screen matching one from earlier, with something else in between,
        # renders again: evidence is read in order, and "same as step 2" nine
        # steps later costs the reader more than the image saves.
        deduper = Deduper()
        deduper.check("a", _text("one"))
        deduper.check("b", _text("two"))
        self.assertIsNone(deduper.check("c", _text("one")))

    def test_forgetting_makes_the_next_identical_screen_render(self) -> None:
        # The failed-render path. Without `forget`, the next identical screen
        # is told to reuse an image that was never produced.
        deduper = Deduper()
        deduper.check("first", _text("hello"))
        deduper.forget()
        self.assertIsNone(deduper.check("second", _text("hello")))

    def test_last_rendered_tracks_the_reusable_label(self) -> None:
        deduper = Deduper()
        self.assertIsNone(deduper.last_rendered)
        deduper.check("first", _text("hello"))
        self.assertEqual("first", deduper.last_rendered)
        deduper.check("second", _text("hello"))
        # Unchanged: the run still points at the first.
        self.assertEqual("first", deduper.last_rendered)
        deduper.check("third", _text("other"))
        self.assertEqual("third", deduper.last_rendered)


if __name__ == "__main__":
    unittest.main()
