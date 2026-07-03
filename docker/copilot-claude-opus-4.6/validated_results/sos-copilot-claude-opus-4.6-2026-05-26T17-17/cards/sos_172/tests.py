"""Tests for SOS 172 — Applied Geometry.

A {2}{G}{U} Sorcery:
  "Create a token that's a copy of target non-Aura permanent you control,
   except it's a 0/0 Fractal creature in addition to its other types.
   Put six +1/+1 counters on it."
"""

from __future__ import annotations

from cards.sos.sos_172.card_impl import AppliedGeometry
from engine.card import Creature, Sorcery, Artifact
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from test_utils import create_game, set_board_state


class TestAppliedGeometryProperties:
    """Static card data should match the SOS 172 spec."""

    def test_is_sorcery(self) -> None:
        card = AppliedGeometry(owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        assert AppliedGeometry(owner=None).name == "Applied Geometry"

    def test_mana_cost(self) -> None:
        card = AppliedGeometry(owner=None)
        assert card.mana_cost == ManaCost.parse("{2}{G}{U}")


class TestAppliedGeometryTargeting:
    """Targets a non-Aura permanent you control."""

    def test_returns_target_requirement(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AppliedGeometry(owner=p1, controller=p1)
        reqs = card.get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)

    def test_target_zone_is_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AppliedGeometry(owner=p1, controller=p1)
        req = card.get_targets(game)[0]
        assert req.zone == Zone.BATTLEFIELD

    def test_target_filter_rejects_aura(self) -> None:
        """Non-Aura permanents only — auras are excluded."""
        from engine.card import Aura
        game = create_game()
        p1 = game.players[0]
        card = AppliedGeometry(owner=p1, controller=p1)
        req = card.get_targets(game)[0]

        aura = Aura(name="Test Aura", owner=p1, controller=p1)
        assert req.filter_fn(aura) is False

    def test_target_filter_accepts_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AppliedGeometry(owner=p1, controller=p1)
        req = card.get_targets(game)[0]

        creature = Creature(name="Bear", owner=p1, controller=p1,
                            base_power=2, base_toughness=2)
        assert req.filter_fn(creature) is True

    def test_target_filter_accepts_artifact(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AppliedGeometry(owner=p1, controller=p1)
        req = card.get_targets(game)[0]

        art = Artifact(name="Sol Ring", owner=p1, controller=p1)
        assert req.filter_fn(art) is True


class TestAppliedGeometryResolution:
    """on_resolve creates a Fractal token copy with six +1/+1 counters."""

    def test_creates_token_on_battlefield(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)

        card = AppliedGeometry(owner=p1, controller=p1)
        card.chosen_targets = [bear]
        card.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, 'is_token', False)]
        assert len(tokens) >= 1

    def test_token_has_six_plus_one_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)

        card = AppliedGeometry(owner=p1, controller=p1)
        card.chosen_targets = [bear]
        card.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, 'is_token', False)]
        assert tokens[0].plus_one_counters == 6

    def test_token_is_fractal_creature(self) -> None:
        """The token should be a 0/0 Fractal creature in addition to other types."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)

        card = AppliedGeometry(owner=p1, controller=p1)
        card.chosen_targets = [bear]
        card.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, 'is_token', False)]
        token = tokens[0]
        assert CardType.CREATURE in token.card_types
        assert "Fractal" in token.subtypes

    def test_token_base_power_toughness_is_zero(self) -> None:
        """The token is a 0/0 regardless of original's P/T."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)

        card = AppliedGeometry(owner=p1, controller=p1)
        card.chosen_targets = [bear]
        card.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, 'is_token', False)]
        token = tokens[0]
        assert token.base_power == 0
        assert token.base_toughness == 0

    def test_token_copies_name(self) -> None:
        """The token should copy the name of the targeted permanent."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Grizzly Bears", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)

        card = AppliedGeometry(owner=p1, controller=p1)
        card.chosen_targets = [bear]
        card.on_resolve(game)

        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, 'is_token', False)]
        token = tokens[0]
        assert token.name == "Grizzly Bears"

    def test_no_target_noop(self) -> None:
        """If no target chosen, resolution should not raise."""
        game = create_game()
        p1 = game.players[0]
        card = AppliedGeometry(owner=p1, controller=p1)
        card.on_resolve(game)  # Should not raise
