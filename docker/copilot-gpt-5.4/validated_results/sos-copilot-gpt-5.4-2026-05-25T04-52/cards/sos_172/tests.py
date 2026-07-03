"""Tests for SOS 172 — Applied Geometry."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_172.card_impl import AppliedGeometry
from benchmarks.sos.workspace.engine.card import Artifact, Aura, Creature, Sorcery
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


def _token_permanents(game: object, player: object) -> list[object]:
    return [
        permanent
        for permanent in game.get_battlefield(player).get_all()
        if getattr(permanent, "is_token", False)
    ]


class TestAppliedGeometryProperties:
    """Static card data should match the SOS 172 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(AppliedGeometry(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = AppliedGeometry(owner=None)

        assert card.name == "Applied Geometry"
        assert card.mana_cost == ManaCost.parse("{2}{G}{U}")


class TestAppliedGeometryTargeting:
    """Applied Geometry should target a non-Aura permanent you control."""

    def test_returns_a_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = AppliedGeometry(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_only_non_aura_permanents_you_control(self) -> None:
        game = create_game()
        p1, p2 = game.players
        spell = AppliedGeometry(owner=p1, controller=p1)
        req = spell.get_targets(game)[0]
        friendly_artifact = Artifact(
            name="Helpful Diagram",
            owner=p1,
            controller=p1,
            subtypes={"Clue"},
        )
        friendly_aura = Aura(name="Attached Lesson", owner=p1, controller=p1)
        opposing_creature = Creature(
            name="Opposing Student",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )

        assert req.filter_fn(friendly_artifact) is True
        assert req.filter_fn(friendly_aura) is False
        assert req.filter_fn(opposing_creature) is False


class TestAppliedGeometryResolution:
    """Applied Geometry should make a six-counter Fractal copy token."""

    def test_on_resolve_creates_a_token_copy_that_is_also_a_fractal_creature_with_six_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target = Artifact(
            name="Helpful Diagram",
            owner=p1,
            controller=p1,
            card_types={CardType.ARTIFACT},
            subtypes={"Clue"},
        )
        set_board_state(game, 0, battlefield=[target])
        spell = AppliedGeometry(owner=p1, controller=p1)
        spell.chosen_targets = [target]

        spell.on_resolve(game)

        tokens = _token_permanents(game, p1)
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert token.name == "Helpful Diagram"
        assert CardType.ARTIFACT in token.card_types
        assert CardType.CREATURE in token.card_types
        assert "Clue" in token.subtypes
        assert "Fractal" in token.subtypes
        assert token.plus_one_counters == 6
        assert token.power == 6
        assert token.toughness == 6
