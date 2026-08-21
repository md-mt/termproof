"""``RecipeMeta`` is reachable without a ``Recipe`` (#199).

The seven descriptive fields describe a scenario the same way whether it is
driven declaratively or by a host's own imperative runner, but they used to be
constructible only as part of a ``Recipe`` — which needs a ``command`` an
imperative host has no single honest value for.

What these tests hold:

- ``Recipe`` is untouched by the split. Its field list, order, defaults and
  positional signature are pinned here, because ``RecipeMeta`` is deliberately
  *not* a base class of it and the reason is exactly that inheritance would
  move those.
- ``RecipeMeta`` and ``Recipe`` agree on all seven names and defaults. Nothing
  in the language holds them together, so this does.
- The default table matches the Rust mirror's, verbatim — see
  ``rust/crates/termproof/tests/recipe_meta.rs::test_defaults_are_the_shared_table``.
"""

from __future__ import annotations

import dataclasses
import unittest

from termproof.models import CommandSpec, Recipe, RecipeMeta

# The seven fields, and the value a recipe file that omits each one gets.
# `name` is the one with no default in the schema; it is empty here rather
# than absent so the table can be compared field for field.
SHARED_DEFAULTS = {
    "name": "",
    "description": "",
    "intent": "",
    "priority": "P2",
    "execution": "scripted",
    "determinism": "deterministic",
    "ci_paths": [],
}


class RecipeMetaTest(unittest.TestCase):
    def test_defaults_are_the_shared_table(self) -> None:
        self.assertEqual(SHARED_DEFAULTS, dataclasses.asdict(RecipeMeta(name="")))

    def test_metadata_is_constructible_without_a_command(self) -> None:
        # The gap #199 is about: this host has no argv to invent.
        meta = RecipeMeta(name="payments", ci_paths=["src/payments/**"], priority="P0")
        self.assertEqual("payments", meta.name)
        self.assertEqual(["src/payments/**"], meta.ci_paths)
        self.assertEqual("deterministic", meta.determinism)

    def test_recipe_and_metadata_declare_the_same_seven_fields(self) -> None:
        # Python cannot express the Rust side's embedding without moving
        # `Recipe`'s fields, so the agreement is asserted rather than derived.
        recipe_fields = {f.name: f for f in dataclasses.fields(Recipe)}
        for meta_field in dataclasses.fields(RecipeMeta):
            with self.subTest(field=meta_field.name):
                self.assertIn(meta_field.name, recipe_fields)
                self.assertEqual(
                    _default_of(recipe_fields[meta_field.name]),
                    _default_of(meta_field),
                )

    def test_a_recipe_hands_over_its_descriptive_half(self) -> None:
        recipe = Recipe(
            name="demo",
            command=CommandSpec(argv=["true"]),
            description="d",
            intent="i",
            priority="P1",
            execution="agent-driven",
            determinism="flaky",
            ci_paths=["src/**"],
        )
        self.assertEqual(
            RecipeMeta(
                name="demo",
                description="d",
                intent="i",
                priority="P1",
                execution="agent-driven",
                determinism="flaky",
                ci_paths=["src/**"],
            ),
            recipe.meta,
        )

    def test_the_handed_over_paths_are_a_copy(self) -> None:
        recipe = Recipe(name="demo", command=CommandSpec(argv=["true"]), ci_paths=["a"])
        recipe.meta.ci_paths.append("b")
        self.assertEqual(["a"], recipe.ci_paths)

    def test_metadata_selects_the_same_way_a_recipe_does(self) -> None:
        from termproof.selection import select_names

        metas = [RecipeMeta(name="smoke"), RecipeMeta(name="payments", ci_paths=["src/payments/**"])]
        self.assertEqual(
            ["smoke", "payments"],
            select_names(
                [(m.name, m.ci_paths) for m in metas],
                ["src/payments/api.rs"],
                always=["smoke"],
            ),
        )


class RecipeIsUnchangedTest(unittest.TestCase):
    """The split must cost ``Recipe`` nothing — including its field order."""

    EXPECTED_FIELDS = [
        "name",
        "command",
        "recipe_version",
        "description",
        "intent",
        "priority",
        "execution",
        "determinism",
        "ci_paths",
        "checks",
        "operator",
        "renderers",
        "steps",
        "assertions",
        "expect_exit_code",
        "timeout_seconds",
        "cols",
        "rows",
        "source_path",
    ]

    def test_field_order_is_unchanged(self) -> None:
        self.assertEqual(
            self.EXPECTED_FIELDS,
            [f.name for f in dataclasses.fields(Recipe)],
        )

    def test_name_and_command_are_still_positional(self) -> None:
        # `RecipeMeta` as a base class would have made `command` keyword-only.
        recipe = Recipe("demo", CommandSpec(argv=["true"]))
        self.assertEqual("demo", recipe.name)
        self.assertEqual(["true"], recipe.command.argv)

    def test_metadata_is_a_property_not_a_field(self) -> None:
        self.assertNotIn("meta", [f.name for f in dataclasses.fields(Recipe)])

    def test_the_type_is_reachable_from_the_package_root(self) -> None:
        # The Rust mirror re-exports `RecipeMeta` at its crate root, so the
        # two front doors match. `rust/crates/termproof/tests/recipe_meta.rs`
        # holds the other side.
        import termproof

        if not hasattr(termproof, "__all__"):
            # `scripts/run_stdlib_tests.py` substitutes a namespace-only
            # `termproof` so `termproof.models` can be loaded without the
            # package's third-party imports. There is no package surface to
            # check under that gate, and the module under test is unaffected.
            self.skipTest("no package root under the stdlib-only gate")
        self.assertIs(termproof.RecipeMeta, RecipeMeta)
        self.assertIn("RecipeMeta", termproof.__all__)


def _default_of(field: dataclasses.Field) -> object:
    """A field's default, calling the factory when there is one."""
    if field.default_factory is not dataclasses.MISSING:
        return field.default_factory()
    return field.default


if __name__ == "__main__":
    unittest.main()
