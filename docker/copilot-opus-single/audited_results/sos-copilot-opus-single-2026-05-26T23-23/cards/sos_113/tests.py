"""Tests for SOS 113 — Emeritus of Conflict // Lightning Bolt.

Emeritus of Conflict is a 2/2 Red Human Wizard for {1}{R} with first strike.
It has a triggered ability: "Whenever you cast your third spell each turn,
this creature becomes prepared."

While prepared, you may cast a copy of Lightning Bolt (deal 3 damage to any
target). Doing so unprepares it.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_113.card_impl import EmeritusOfConflictLightningBolt
from engine.card import Creature, Instant
from engine.events import SpellCastTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestEmeritusOfConflictProperties:
    """The creature face should have correct static characteristics."""

    def test_is_creature(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert card.name == "Emeritus of Conflict"

    def test_mana_cost(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_power_toughness(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_first_strike(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert Keyword.FIRST_STRIKE in card.keywords


# ---------------------------------------------------------------------------
# Prepared state — initial
# ---------------------------------------------------------------------------


class TestEmeritusOfConflictPreparedState:
    """The creature should not start prepared."""

    def test_not_prepared_initially(self) -> None:
        card = EmeritusOfConflictLightningBolt(owner=None)
        assert card.is_prepared is False


# ---------------------------------------------------------------------------
# Triggered ability — third spell each turn
# ---------------------------------------------------------------------------


class TestEmeritusOfConflictTrigger:
    """Whenever you cast your third spell each turn, becomes prepared."""

    def test_does_not_prepare_on_first_spell(self) -> None:
        """Casting only one spell should not prepare the creature."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        # Simulate casting first spell
        game.spells_cast_this_turn = game.spells_cast_this_turn if hasattr(game, 'spells_cast_this_turn') else {}
        dummy = Creature(name="Dummy Spell", owner=game.players[0], base_power=1, base_toughness=1)
        event = SpellCastTriggeredEvent(spell=dummy, player=game.players[0],
                                        card=dummy, controller=game.players[0])
        card.on_spell_cast(game, event)
        assert card.is_prepared is False

    def test_does_not_prepare_on_second_spell(self) -> None:
        """Casting only two spells should not prepare the creature."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        dummy = Creature(name="Dummy Spell", owner=game.players[0], base_power=1, base_toughness=1)
        event = SpellCastTriggeredEvent(spell=dummy, player=game.players[0],
                                        card=dummy, controller=game.players[0])
        card.on_spell_cast(game, event)
        card.on_spell_cast(game, event)
        assert card.is_prepared is False

    def test_prepares_on_third_spell(self) -> None:
        """Casting the third spell should make the creature prepared."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        dummy = Creature(name="Dummy Spell", owner=game.players[0], base_power=1, base_toughness=1)
        event = SpellCastTriggeredEvent(spell=dummy, player=game.players[0],
                                        card=dummy, controller=game.players[0])
        card.on_spell_cast(game, event)
        card.on_spell_cast(game, event)
        card.on_spell_cast(game, event)
        assert card.is_prepared is True

    def test_does_not_prepare_on_opponent_third_spell(self) -> None:
        """Opponent's spells should not count toward our trigger."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        dummy = Creature(name="Dummy Spell", owner=game.players[1], base_power=1, base_toughness=1)
        event = SpellCastTriggeredEvent(spell=dummy, player=game.players[1],
                                        card=dummy, controller=game.players[1])
        card.on_spell_cast(game, event)
        card.on_spell_cast(game, event)
        card.on_spell_cast(game, event)
        assert card.is_prepared is False

    def test_fourth_spell_does_not_double_prepare(self) -> None:
        """Casting a fourth spell should not re-trigger preparation."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        dummy = Creature(name="Dummy Spell", owner=game.players[0], base_power=1, base_toughness=1)
        event = SpellCastTriggeredEvent(spell=dummy, player=game.players[0],
                                        card=dummy, controller=game.players[0])
        # Cast three spells — becomes prepared
        for _ in range(3):
            card.on_spell_cast(game, event)
        assert card.is_prepared is True

        # Cast a fourth spell — still prepared, no error
        card.on_spell_cast(game, event)
        assert card.is_prepared is True


# ---------------------------------------------------------------------------
# Prepared spell — Lightning Bolt
# ---------------------------------------------------------------------------


class TestEmeritusOfConflictLightningBoltSpell:
    """While prepared, casting the spell deals 3 damage to any target."""

    def _prepare_card(self, game, card):
        """Helper to prepare the card by simulating three spell casts."""
        dummy = Creature(name="Dummy Spell", owner=game.players[0], base_power=1, base_toughness=1)
        event = SpellCastTriggeredEvent(spell=dummy, player=game.players[0],
                                        card=dummy, controller=game.players[0])
        for _ in range(3):
            card.on_spell_cast(game, event)

    def test_lightning_bolt_deals_3_damage_to_player(self) -> None:
        """Lightning Bolt should deal 3 damage to a target player."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        self._prepare_card(game, card)
        assert card.is_prepared is True

        life_before = game.players[1].life
        card.cast_prepared_spell(game, target=game.players[1])
        assert game.players[1].life == life_before - 3

    def test_lightning_bolt_deals_3_damage_to_creature(self) -> None:
        """Lightning Bolt should deal 3 damage to a target creature."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        target_creature = Creature(name="Target Bear", owner=game.players[1],
                                   controller=game.players[1],
                                   base_power=2, base_toughness=4)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target_creature])

        self._prepare_card(game, card)

        damage_before = getattr(target_creature, 'damage_marked', 0)
        card.cast_prepared_spell(game, target=target_creature)
        assert target_creature.damage_marked == damage_before + 3

    def test_casting_spell_unprepares(self) -> None:
        """Casting the prepared spell should unprepare the creature."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        self._prepare_card(game, card)
        assert card.is_prepared is True

        card.cast_prepared_spell(game, target=game.players[1])
        assert card.is_prepared is False

    def test_cannot_cast_spell_when_not_prepared(self) -> None:
        """Should not be able to cast the spell if not prepared."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        set_board_state(game, 0, battlefield=[card])

        assert card.is_prepared is False
        with pytest.raises((ValueError, RuntimeError, AttributeError)):
            card.cast_prepared_spell(game, target=game.players[1])

    def test_lightning_bolt_kills_3_toughness_creature(self) -> None:
        """Lightning Bolt dealing 3 to a 3-toughness creature should kill it."""
        game = create_game()
        card = EmeritusOfConflictLightningBolt(owner=game.players[0])
        card.controller = game.players[0]
        target_creature = Creature(name="Hill Giant", owner=game.players[1],
                                   controller=game.players[1],
                                   base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target_creature])

        self._prepare_card(game, card)
        card.cast_prepared_spell(game, target=target_creature)

        # 3 damage to 3 toughness creature = lethal
        assert target_creature.damage_marked >= target_creature.base_toughness
