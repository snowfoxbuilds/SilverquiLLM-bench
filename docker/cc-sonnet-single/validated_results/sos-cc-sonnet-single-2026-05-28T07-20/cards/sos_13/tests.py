"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Requirements under test:
1. Static properties: Legendary Creature — Cat Cleric, 3/3, mana cost {1}{W}{W}.
2. ETB trigger: target player creates a 1/1 white-and-black Inkling creature
   token with flying.
3. ETB trigger: after token creation, if an opponent controls more creatures
   than you, this creature becomes prepared (is_prepared = True).
4. ETB trigger: if opponent does NOT control more creatures than you, creature
   is NOT prepared after resolution.
5. is_prepared attribute starts as False.
6. When prepared, can cast a copy of its spell (Swords to Plowshares:
   exile target creature, controller gains life equal to its power).
7. Casting the copy while prepared sets is_prepared back to False.
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature
from engine.events import EntersBattlefieldTriggeredEvent
from engine.triggers import TriggerRegistration
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_creature(name: str, power: int = 2, toughness: int = 2) -> Creature:
    """Return a minimal vanilla creature for board state setup."""
    c = Creature(name=name, base_power=power, base_toughness=toughness)
    c.card_types = {CardType.CREATURE}
    return c


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------

class TestEmeritusProperties:
    """Static characteristics should match the SOS 13 card spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        # The front-face name or the full DFC name — either is valid.
        assert "Emeritus of Truce" in card.name

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_base_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_base_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_is_legendary(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert Supertype.LEGENDARY in card.supertypes

    def test_has_cat_subtype(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes

    def test_has_cleric_subtype(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cleric" in card.subtypes

    def test_creature_card_type(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_color_is_white(self) -> None:
        """Front face is white ({1}{W}{W})."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        cost = card.mana_cost
        assert cost.pips.get(ManaType.WHITE, 0) >= 2


# ---------------------------------------------------------------------------
# Prepared mechanic — initial state
# ---------------------------------------------------------------------------

class TestEmeritusInitialState:
    """Card starts unprepared."""

    def test_is_prepared_defaults_to_false(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.is_prepared is False

    def test_is_prepared_is_accessible(self) -> None:
        """is_prepared attribute must exist before any trigger fires."""
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert hasattr(card, "is_prepared")


# ---------------------------------------------------------------------------
# ETB trigger — registration
# ---------------------------------------------------------------------------

class TestEmeritusETBTriggerRegistration:
    """register_triggers() must wire an EntersBattlefieldTriggeredEvent trigger."""

    def test_registers_at_least_one_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_registered_trigger_watches_etb_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(card)
        event_types = [t.event_type for t in triggers]
        assert EntersBattlefieldTriggeredEvent in event_types

    def test_trigger_condition_fires_for_self(self) -> None:
        """ETB condition must match when the card itself is the permanent."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        etb_triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert etb_triggers, "No ETB trigger registered"
        trigger = etb_triggers[0]

        event_self = EntersBattlefieldTriggeredEvent(permanent=card, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event_self) is True

    def test_trigger_condition_does_not_fire_for_other_permanent(self) -> None:
        """ETB condition must NOT match when a different permanent enters."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        etb_triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert etb_triggers, "No ETB trigger registered"
        trigger = etb_triggers[0]

        other = _make_creature("Other Bear")
        event_other = EntersBattlefieldTriggeredEvent(permanent=other, controller=p1)
        if trigger.condition is not None:
            assert trigger.condition(game, event_other) is False


# ---------------------------------------------------------------------------
# ETB trigger effect — Inkling token creation
# ---------------------------------------------------------------------------

class TestEmeritusInklingTokenCreation:
    """ETB effect creates a 1/1 white-and-black Inkling with flying for target player."""

    def _get_etb_effect(self, game, card):
        """Helper: return the ETB trigger effect callable."""
        etb_triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert etb_triggers, "No ETB trigger registered"
        return etb_triggers[0].effect

    def test_etb_effect_creates_token_for_controller(self) -> None:
        """After ETB effect fires with no scripted target, controller gets a token."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        # Count creatures on battlefield before
        before = len([
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature)
        ])
        effect = self._get_etb_effect(game, card)
        effect(game)

        # At least one token should have been created somewhere (for p1 or p2)
        after_p1 = len([
            obj for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature)
        ])
        after_p2 = len([
            obj for obj in game.get_battlefield(game.players[1]).get_all()
            if isinstance(obj, Creature)
        ])
        assert (after_p1 + after_p2) > before

    def test_etb_creates_exactly_one_token(self) -> None:
        """ETB effect creates exactly one Inkling token."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        bf1_before = len(game.get_battlefield(p1).get_all())
        bf2_before = len(game.get_battlefield(p2).get_all())
        effect = self._get_etb_effect(game, card)
        effect(game)

        bf1_after = len(game.get_battlefield(p1).get_all())
        bf2_after = len(game.get_battlefield(p2).get_all())
        total_new = (bf1_after - bf1_before) + (bf2_after - bf2_before)
        assert total_new == 1

    def test_inkling_token_is_one_one(self) -> None:
        """The created token is a 1/1 creature."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        effect = self._get_etb_effect(game, card)
        effect(game)

        # Collect all tokens from both players' battlefields
        all_creatures = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if getattr(obj, "is_token", False) and isinstance(obj, Creature):
                    all_creatures.append(obj)

        assert len(all_creatures) >= 1
        token = all_creatures[-1]
        assert token.base_power == 1
        assert token.base_toughness == 1

    def test_inkling_token_has_inkling_subtype(self) -> None:
        """The token has the 'Inkling' subtype."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        effect = self._get_etb_effect(game, card)
        effect(game)

        tokens = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if getattr(obj, "is_token", False) and isinstance(obj, Creature):
                    tokens.append(obj)

        assert tokens, "No token was created"
        token = tokens[-1]
        assert "Inkling" in getattr(token, "subtypes", set())

    def test_inkling_token_has_flying(self) -> None:
        """The Inkling token has the Flying keyword."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)

        effect = self._get_etb_effect(game, card)
        effect(game)

        tokens = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if getattr(obj, "is_token", False) and isinstance(obj, Creature):
                    tokens.append(obj)

        assert tokens, "No token was created"
        token = tokens[-1]
        assert Keyword.FLYING in getattr(token, "keywords", Keyword(0))


# ---------------------------------------------------------------------------
# ETB trigger — prepared condition
# ---------------------------------------------------------------------------

class TestEmeritusBecomesPreared:
    """After ETB effect, card becomes prepared only if opponent controls more creatures."""

    def _fire_etb(self, game, card) -> None:
        """Fire the ETB effect directly."""
        triggers = [
            t for t in game.trigger_manager.get_triggers_for_source(card)
            if t.event_type is EntersBattlefieldTriggeredEvent
        ]
        assert triggers, "No ETB trigger registered"
        triggers[0].effect(game)

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """If opponent controls more creatures after token, card becomes prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put Emeritus on p1's battlefield (so p1 controls it)
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        game.get_battlefield(p1).add(card)

        # Give p2 two creatures to outnumber p1's after token creation
        opp_creature1 = _make_creature("Opp Bear 1")
        opp_creature2 = _make_creature("Opp Bear 2")
        opp_creature3 = _make_creature("Opp Bear 3")
        set_board_state(game, 1, battlefield=[opp_creature1, opp_creature2, opp_creature3])

        card.register_triggers(game)
        # p1 has 1 creature (card itself); p2 has 3 — ETB creates 1 token for p1 → p1 has 2, p2 has 3
        self._fire_etb(game, card)

        assert card.is_prepared is True

    def test_not_prepared_when_opponent_does_not_have_more_creatures(self) -> None:
        """If controller has >= creatures as opponent after token, not prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # p1 controls Emeritus plus many creatures
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        extra1 = _make_creature("Extra 1")
        extra2 = _make_creature("Extra 2")
        extra3 = _make_creature("Extra 3")
        set_board_state(game, 0, battlefield=[card, extra1, extra2, extra3])

        # p2 has only 1 creature — p1 has many more
        opp = _make_creature("Lone Opp")
        set_board_state(game, 1, battlefield=[opp])

        card.register_triggers(game)
        # After ETB, p1 has 5 (card + 3 + 1 token), p2 has 1 → not prepared
        self._fire_etb(game, card)

        assert card.is_prepared is False

    def test_not_prepared_when_opponent_has_equal_creatures(self) -> None:
        """Exact tie in creature count → not prepared (opponent must control MORE)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1 will have card + 1 token = 2 after ETB
        set_board_state(game, 0, battlefield=[card])
        # p2 has exactly 2 (so they'll tie after token)
        opp1 = _make_creature("Opp Tie 1")
        opp2 = _make_creature("Opp Tie 2")
        set_board_state(game, 1, battlefield=[opp1, opp2])

        card.register_triggers(game)
        self._fire_etb(game, card)

        # Tie: p1 has 2 (card + token), p2 has 2 → not prepared
        assert card.is_prepared is False

    def test_starts_not_prepared_before_etb_fires(self) -> None:
        """Even after register_triggers, card is not prepared until ETB resolves."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.register_triggers(game)
        assert card.is_prepared is False


# ---------------------------------------------------------------------------
# Swords to Plowshares spell copy — effect when prepared
# ---------------------------------------------------------------------------

class TestEmeritusSpellCopyEffect:
    """When prepared, casting the STP copy exiles a creature and
    grants life; doing so unprepares the card."""

    def _prepare(self, card) -> None:
        """Manually set a card's prepared state for isolated testing."""
        card.is_prepared = True

    def test_cast_spell_copy_exiles_target_creature(self) -> None:
        """STP effect: target creature is exiled from the battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = _make_creature("Target Bear", power=3, toughness=3)
        target.owner = p2
        target.controller = p2
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        self._prepare(card)

        card.cast_prepared_spell(game, target)

        # Creature must no longer be on the battlefield
        assert not game.get_battlefield(p2).contains(target)
        # Creature must be in exile
        assert game.get_exile(p2).contains(target)

    def test_cast_spell_copy_grants_life_equal_to_power(self) -> None:
        """Controller of exiled creature gains life equal to its power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = _make_creature("Big Bear", power=5, toughness=5)
        target.owner = p2
        target.controller = p2
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        self._prepare(card)
        life_before = p2.life

        card.cast_prepared_spell(game, target)

        assert p2.life == life_before + 5

    def test_cast_prepared_spell_unprepares_card(self) -> None:
        """After casting the copy, is_prepared is set to False."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = _make_creature("Bear", power=2, toughness=2)
        target.owner = p2
        target.controller = p2
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        self._prepare(card)
        assert card.is_prepared is True

        card.cast_prepared_spell(game, target)

        assert card.is_prepared is False

    def test_cast_prepared_spell_zero_power_gains_no_life(self) -> None:
        """A 0-power creature grants 0 life — no negative life gain."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = _make_creature("Wall", power=0, toughness=5)
        target.owner = p2
        target.controller = p2
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        self._prepare(card)
        life_before = p2.life

        card.cast_prepared_spell(game, target)

        assert p2.life == life_before  # no life gained

    def test_cannot_cast_prepared_spell_when_not_prepared(self) -> None:
        """Calling cast_prepared_spell when not prepared is a no-op or raises cleanly."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = _make_creature("Innocent Bear")
        target.owner = p2
        target.controller = p2
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # is_prepared is False by default
        life_before = p2.life

        # Should either do nothing or raise; must not crash with unhandled error.
        try:
            card.cast_prepared_spell(game, target)
        except Exception:
            pass  # raising is acceptable

        # Creature should not be exiled (effect did not fire)
        assert not game.get_exile(p2).contains(target)
        # Life unchanged
        assert p2.life == life_before

    def test_life_gained_matches_power_at_exile_time(self) -> None:
        """Life gained equals the creature's power at the time of exile."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = _make_creature("Counter Bear", power=4, toughness=4)
        target.owner = p2
        target.controller = p2
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        self._prepare(card)
        life_before = p2.life

        card.cast_prepared_spell(game, target)

        assert p2.life == life_before + 4
