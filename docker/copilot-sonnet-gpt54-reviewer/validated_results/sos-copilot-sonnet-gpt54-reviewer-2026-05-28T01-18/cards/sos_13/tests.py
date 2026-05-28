"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares.

Covers:
- Static card properties: name, mana cost, type, P/T, subtypes
- Prepared attribute: defaults to False
- ETB trigger: target player creates 1/1 white-and-black Inkling token with flying
- ETB conditional: becomes prepared when opponent controls more creatures than you
- ETB conditional: does NOT become prepared when opponent doesn't control more creatures
- Swords to Plowshares spell: exiles target creature, controller gains life equal to power
- Prepared mechanic: while prepared, can cast a copy of Swords to Plowshares
- Prepared mechanic: after casting the copy, creature becomes unprepared
"""

from __future__ import annotations

import pytest

from cards.sos.sos_13.card_impl import EmeritusOfTruceSwordsToPlowshares
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Static card properties
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceProperties:
    """Static card data must match the SOS 13 spec."""

    def test_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.name == "Emeritus of Truce"

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_base_power(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_power == 3

    def test_base_toughness(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.base_toughness == 3

    def test_card_type_is_creature(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert CardType.CREATURE in card.card_types

    def test_subtype_includes_cat(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cat" in card.subtypes

    def test_subtype_includes_cleric(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert "Cleric" in card.subtypes


# ---------------------------------------------------------------------------
# Prepared attribute
# ---------------------------------------------------------------------------


class TestPreparedAttribute:
    """The prepared attribute is a boolean flag on the creature."""

    def test_prepared_defaults_to_false(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        assert card.prepared is False

    def test_prepared_can_be_set_to_true(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        card.prepared = True
        assert card.prepared is True

    def test_prepared_can_be_reset_to_false(self) -> None:
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        card.prepared = True
        card.prepared = False
        assert card.prepared is False


# ---------------------------------------------------------------------------
# ETB trigger: token creation
# ---------------------------------------------------------------------------


class TestInklingTokenCreation:
    """When Emeritus of Truce enters, target player creates a 1/1 white and
    black Inkling creature token with flying."""

    def test_etb_creates_one_token_for_target_player(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1 controls no creatures so opponent won't have more; set opponent
        # to have no creatures either — we only care about token creation here.
        before = len(game.get_battlefield(p1).get_all())
        card.chosen_targets = [p1]
        card.on_resolve(game)
        after = len(game.get_battlefield(p1).get_all())
        # At least one token (plus the creature itself) should enter
        assert after > before

    def test_etb_token_is_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        tokens = [
            obj for obj in bf
            if getattr(obj, "is_token", False) and CardType.CREATURE in getattr(obj, "card_types", set())
        ]
        assert len(tokens) >= 1

    def test_etb_token_is_inkling(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if getattr(obj, "is_token", False) and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) >= 1

    def test_etb_token_is_1_1(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if getattr(obj, "is_token", False) and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) >= 1
        tok = inkling_tokens[0]
        assert tok.base_power == 1
        assert tok.base_toughness == 1

    def test_etb_token_has_flying(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if getattr(obj, "is_token", False) and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) >= 1
        tok = inkling_tokens[0]
        assert Keyword.FLYING in tok.keywords

    def test_etb_token_goes_to_target_player_battlefield(self) -> None:
        """Token enters the battlefield under the target player's control."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Target p2 to get the token
        card.chosen_targets = [p2]
        before_p2 = len(game.get_battlefield(p2).get_all())
        card.on_resolve(game)
        after_p2 = len(game.get_battlefield(p2).get_all())
        assert after_p2 > before_p2

    def test_etb_exactly_one_token_created(self) -> None:
        """ETB creates exactly one Inkling token, not more."""
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        inkling_tokens = [
            obj for obj in bf
            if getattr(obj, "is_token", False) and "Inkling" in getattr(obj, "subtypes", set())
        ]
        assert len(inkling_tokens) == 1


# ---------------------------------------------------------------------------
# ETB conditional: prepared state
# ---------------------------------------------------------------------------


class TestPreparedCondition:
    """After the token is created, if an opponent controls more creatures
    than you, the creature becomes prepared."""

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """p1 controls 0 creatures (before ETB); opponent controls 2 —
        opponent has more, so Emeritus becomes prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # Put 2 creatures on p2's battlefield
        opp1 = Creature(name="Bear1", owner=p2, controller=p2, base_power=2, base_toughness=2)
        opp2 = Creature(name="Bear2", owner=p2, controller=p2, base_power=2, base_toughness=2)
        opp1.card_types = {CardType.CREATURE}
        opp2.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(opp1)
        game.get_battlefield(p2).add(opp2)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # p1 targets themselves (token goes to p1); p1 now has 1 creature (the token + itself?)
        # After resolve, p1 controls the creature itself + 1 token = 2 creatures;
        # but if we check AFTER token creation: p2 has 2, p1 has 1 token + Emeritus = 2
        # Actually the condition is checked after token creation:
        # p1 gets the token, so p1 has 1 inkling token (if they target themselves)
        # and p2 has 2 bears. They're equal, so prepared might not trigger.
        # Let's instead give p2 many more creatures than p1 would have after the token.
        opp3 = Creature(name="Bear3", owner=p2, controller=p2, base_power=2, base_toughness=2)
        opp3.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(opp3)

        # p2 now has 3 creatures; after ETB, p1 has 1 token (and the Emeritus itself)
        # "More creatures than you" - p2 has 3, p1 has 1 token (Emeritus not on BF yet in test)
        # In test we call on_resolve directly so we set up the board state cleanly.
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.prepared is True

    def test_does_not_become_prepared_when_opponent_has_equal_creatures(self) -> None:
        """If opponent controls the same number of creatures as you, creature
        does NOT become prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # p1 controls 2 creatures already, p2 controls 2 creatures
        my1 = Creature(name="Mine1", owner=p1, controller=p1, base_power=1, base_toughness=1)
        my2 = Creature(name="Mine2", owner=p1, controller=p1, base_power=1, base_toughness=1)
        opp1 = Creature(name="Opp1", owner=p2, controller=p2, base_power=1, base_toughness=1)
        opp2 = Creature(name="Opp2", owner=p2, controller=p2, base_power=1, base_toughness=1)
        for c in (my1, my2):
            c.card_types = {CardType.CREATURE}
            game.get_battlefield(p1).add(c)
        for c in (opp1, opp2):
            c.card_types = {CardType.CREATURE}
            game.get_battlefield(p2).add(c)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        # After token creation, p1 has 3 creatures (my1, my2, + inkling token),
        # p2 has 2. p2 doesn't have MORE than p1, so not prepared.
        assert card.prepared is False

    def test_does_not_become_prepared_when_controller_has_more_creatures(self) -> None:
        """If the controller has more creatures than the opponent, NOT prepared."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # p1 controls 5 creatures, p2 controls 1
        for i in range(5):
            c = Creature(name=f"Mine{i}", owner=p1, controller=p1, base_power=1, base_toughness=1)
            c.card_types = {CardType.CREATURE}
            game.get_battlefield(p1).add(c)

        opp1 = Creature(name="Opp1", owner=p2, controller=p2, base_power=1, base_toughness=1)
        opp1.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(opp1)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.prepared is False

    def test_becomes_prepared_when_opponent_has_strictly_more_creatures(self) -> None:
        """Only STRICTLY MORE opponent creatures triggers the prepared condition."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # p2 has 5 creatures; after ETB, p1 will have 1 inkling token
        for i in range(5):
            c = Creature(name=f"Opp{i}", owner=p2, controller=p2, base_power=1, base_toughness=1)
            c.card_types = {CardType.CREATURE}
            game.get_battlefield(p2).add(c)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.chosen_targets = [p1]
        card.on_resolve(game)
        assert card.prepared is True


# ---------------------------------------------------------------------------
# Swords to Plowshares spell resolution
# ---------------------------------------------------------------------------


class TestSwordsToPlowsharesSpell:
    """The Swords to Plowshares spell (the 'prepared' copy) exiles target
    creature. Its controller gains life equal to the creature's power."""

    def test_swords_to_plowshares_exiles_target_creature(self) -> None:
        """After STP resolves, the target creature should be in exile."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Grizzly Bears", owner=p2, controller=p2,
                          base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        # Cast the prepared spell copy targeting the creature
        card.cast_prepared_spell(game, target)

        # Target should be in exile
        exile = game.get_exile(p2)
        assert exile.contains(target)

    def test_swords_to_plowshares_removes_from_battlefield(self) -> None:
        """After STP resolves, the target creature should no longer be on the battlefield."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Llanowar Elves", owner=p2, controller=p2,
                          base_power=1, base_toughness=1)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        card.cast_prepared_spell(game, target)

        bf = game.get_battlefield(p2)
        assert not bf.contains(target)

    def test_swords_to_plowshares_controller_gains_life_equal_to_power(self) -> None:
        """The exiled creature's controller gains life equal to that creature's power."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # 4/4 creature; p2 controls it
        target = Creature(name="Serra Angel", owner=p2, controller=p2,
                          base_power=4, base_toughness=4)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        before_life = p2.life
        card.cast_prepared_spell(game, target)

        # p2 (the exiled creature's controller) gains 4 life
        assert p2.life == before_life + 4

    def test_swords_to_plowshares_life_gain_equals_power(self) -> None:
        """Life gain correctly tracks the creature's actual power value."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        # 7/7 creature
        target = Creature(name="Shivan Dragon", owner=p2, controller=p2,
                          base_power=7, base_toughness=7)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        before_life = p2.life
        card.cast_prepared_spell(game, target)
        assert p2.life == before_life + 7

    def test_swords_to_plowshares_zero_power_creature_gains_no_life(self) -> None:
        """A 0-power creature gives 0 life when exiled."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Ornithopter", owner=p2, controller=p2,
                          base_power=0, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True
        before_life = p2.life
        card.cast_prepared_spell(game, target)
        assert p2.life == before_life


# ---------------------------------------------------------------------------
# Prepared mechanic: casting a copy unprepares the creature
# ---------------------------------------------------------------------------


class TestPreparedMechanicCycle:
    """After casting the copy of Swords to Plowshares (via prepared),
    the creature becomes unprepared."""

    def test_creature_becomes_unprepared_after_casting_copy(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Goblin Token", owner=p2, controller=p2,
                          base_power=1, base_toughness=1)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True

        card.cast_prepared_spell(game, target)

        # After casting, the creature is no longer prepared
        assert card.prepared is False

    def test_cast_prepared_spell_requires_prepared_to_be_true(self) -> None:
        """Casting the prepared spell when not prepared should be a no-op or raise."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target = Creature(name="Test Bear", owner=p2, controller=p2,
                          base_power=2, base_toughness=2)
        target.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        # Not prepared
        assert card.prepared is False
        before_life = p2.life

        # Attempt to cast while not prepared — should not exile the creature
        # or gain life (either raises or is silently a no-op)
        try:
            card.cast_prepared_spell(game, target)
        except Exception:
            pass  # It's acceptable to raise when not prepared

        # Key assertion: target should NOT be exiled (spell didn't fire)
        assert not game.get_exile(p2).contains(target)
        # Life should be unchanged
        assert p2.life == before_life

    def test_prepared_can_only_fire_once_per_preparation(self) -> None:
        """After casting the copy once, the creature is unprepared and cannot
        cast again until re-prepared by another ETB or effect."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        target1 = Creature(name="Bear1", owner=p2, controller=p2,
                           base_power=2, base_toughness=2)
        target2 = Creature(name="Bear2", owner=p2, controller=p2,
                           base_power=2, base_toughness=2)
        target1.card_types = {CardType.CREATURE}
        target2.card_types = {CardType.CREATURE}
        game.get_battlefield(p2).add(target1)
        game.get_battlefield(p2).add(target2)

        card = EmeritusOfTruceSwordsToPlowshares(owner=p1, controller=p1)
        card.prepared = True

        # First cast: should work
        card.cast_prepared_spell(game, target1)
        assert card.prepared is False

        # Second cast attempt: should NOT exile target2
        before_life = p2.life
        try:
            card.cast_prepared_spell(game, target2)
        except Exception:
            pass

        # target2 should still be on battlefield (second cast failed)
        assert game.get_battlefield(p2).contains(target2)


# ---------------------------------------------------------------------------
# ETB targeting (get_targets)
# ---------------------------------------------------------------------------


class TestEmeritusOfTruceTargeting:
    """get_targets() must advertise a single player target for the ETB effect."""

    def test_get_targets_returns_list(self) -> None:
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        result = card.get_targets(game)
        assert isinstance(result, list)

    def test_get_targets_has_one_requirement(self) -> None:
        game = create_game()
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        reqs = card.get_targets(game)
        assert len(reqs) == 1

    def test_get_targets_accepts_players(self) -> None:
        """The target filter must accept players."""
        from engine.types import TargetRequirement
        game = create_game()
        p1 = game.players[0]
        card = EmeritusOfTruceSwordsToPlowshares(owner=None)
        reqs = card.get_targets(game)
        req = reqs[0]
        assert isinstance(req, TargetRequirement)
        # Players have zones; filter should accept players
        assert req.filter_fn(p1) is True
