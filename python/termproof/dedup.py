"""Not re-rendering a screen that has not changed.

A recipe captures evidence either side of an action, and plenty of actions turn
out not to change the screen — a key that was already pressed, a wait that had
nothing to wait for, a step that failed to do anything. Rendering and uploading
a byte-identical image for each of those is pure cost, and a reviewer scrolling
twelve identical images is worse off than one reading four distinct ones.

:class:`Deduper` is where that rule lives, once, for the whole package. Both
callers ask it the question and neither answers it itself:

* :meth:`termproof.collector.EvidenceCollector.publish`, which publishes what a
  caller captured while the run was going on;
* :func:`termproof.evidence.render_artifacts`, which renders the steps a
  finished :class:`~termproof.models.RunResult` already carries.

The two write different documents — ``evidence.json`` with ``same_as`` against
``steps-manifest.json`` with ``unchanged_from_previous`` — but "has this screen
changed since the last one I rendered?" is one question, and answering it in two
places is how the two answers drift apart.

Mirrors ``termproof::evidence::dedup::Deduper``. The Python package flattens the
Rust ``evidence::`` namespace into top-level modules, which is why
``evidence::dedup`` lands here rather than inside :mod:`termproof.evidence`.

Attributes count
----------------

Deduplication keys on
:meth:`~termproof.attributed.AttributedScreen.render_fingerprint`, not on text.
Two screens with the same characters but a different highlight are *different
screenshots*, and a text-keyed cache would silently collapse them — losing
exactly the frame where a selection moved.

It only ever looks backwards one step
-------------------------------------

A run of identical screens all point at the first of them, but a screen that
matches one from earlier — after something else in between — renders again. That
is deliberate: evidence is read in order, and a caption saying "same as step 2"
nine steps later costs the reader more than the image saves.

.. code-block:: python

    from termproof.attributed import attributed_screen_from_text
    from termproof.dedup import Deduper

    deduper = Deduper()
    menu = attributed_screen_from_text("menu open", columns=20, rows=2)
    same = attributed_screen_from_text("menu open", columns=20, rows=2)
    gone = attributed_screen_from_text("menu closed", columns=20, rows=2)

    assert deduper.check("opened", menu) is None
    assert deduper.check("still-open", same) == "opened"
    assert deduper.check("closed", gone) is None
"""

from __future__ import annotations

from dataclasses import dataclass

from .attributed import AttributedScreen


@dataclass(frozen=True)
class _Rendered:
    """The screen a reuse verdict would point at."""

    label: str
    fingerprint: str


class Deduper:
    """Decides whether a screen needs rendering, or matches the previous one."""

    def __init__(self) -> None:
        self._previous: _Rendered | None = None

    def check(self, label: str, screen: AttributedScreen) -> str | None:
        """Whether ``screen`` duplicates the previously rendered one.

        Returns the ``label`` the caller gave the step to reuse, or ``None``
        when this screen needs rendering. A ``None`` answer records the screen
        as the new previous, so a run of identical screens all point at the
        first.

        The caller renders on ``None`` and, if that render *fails*, should call
        :meth:`forget` — otherwise the next identical screen would be told to
        reuse an image that does not exist.
        """
        fingerprint = screen.render_fingerprint()
        previous = self._previous
        if previous is not None and previous.fingerprint == fingerprint:
            # Deliberately not updating `_previous`: every screen in a run of
            # identical ones points at the first, not at its neighbour.
            return previous.label
        self._previous = _Rendered(label=label, fingerprint=fingerprint)
        return None

    def forget(self) -> None:
        """Drop the remembered screen, so the next one renders afresh.

        For the case where the caller was told to render and could not. Without
        this, a failed render leaves a fingerprint pointing at an image that was
        never produced, and the next identical screen reuses nothing.
        """
        self._previous = None

    @property
    def last_rendered(self) -> str | None:
        """The label of the last screen that needed rendering, if any."""
        return None if self._previous is None else self._previous.label


__all__ = ["Deduper"]
