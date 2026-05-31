"""Tests for Emeritus of Truce // Swords to Plowshares (SOS #13)."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruce
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_battlefield_creatures(game, player_index: int) -> list:
    bf = game.get_battlefield(game.players[player_index])
    return [c for c in bf.get_all() if CardType.CREATURE in getattr(c, "card_types", set())]


def _resolve_stack(game) -> None:
    """Resolve all items on the stack without priority-passing overhead."""
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _put_on_battlefield(game, player_index: int, card, *, token_target=None) -> None:
    """Put a card onto the battlefield and resolve its ETB trigger.

    Registers triggers BEFORE firing ETB so self-referencing ETB triggers
    (``event.permanent is source``) fire correctly.

    Args:
        token_target: Override which player receives the Inkling token.
            Stored on the card as ``_etb_target_player`` so the ETB effect
            can pick it up without needing a scripted player.choose() call.
    """
    from engine.events import EntersBattlefieldTriggeredEvent

    player = game.players[player_index]
    card.owner = player
    card.controller = player
    if token_target is not None:
        card._etb_target_player = token_target
    bf = game.get_battlefield(player)
    bf.add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)
    if hasattr(card, "register_replacement_effects"):
        card.register_replacement_effects(game)
    game.trigger_manager.fire_event(
        game,
        EntersBattlefieldTriggeredEvent(permanent=card, controller=player),
    )
    _resolve_stack(game)


# ---------------------------------------------------------------------------
# Card attribute tests
# ---------------------------------------------------------------------------

class TestCardAttributes:
    def test_name(self):
        card = EmeritusOfTruce()
        assert card.name == "Emeritus of Truce"

    def test_power_toughness(self):
        card = EmeritusOfTruce()
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_power_toughness_property(self):
        card = EmeritusOfTruce()
        assert card.power == 3
        assert card.toughness == 3

    def test_card_type_is_creature(self):
        card = EmeritusOfTruce()
        assert CardType.CREATURE in card.card_types

    def test_subtypes_cat_cleric(self):
        card = EmeritusOfTruce()
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_mana_cost(self):
        card = EmeritusOfTruce()
        assert card.mana_cost.pips.get(ManaType.WHITE, 0) == 2
        assert card.mana_cost.generic == 1

    def test_not_prepared_by_default(self):
        card = EmeritusOfTruce()
        assert card.is_prepared is False


# ---------------------------------------------------------------------------
# ETB trigger: Inkling token creation
# ---------------------------------------------------------------------------

class TestETBInklingToken:
    def test_etb_creates_inkling_token_for_controller(self):
        """ETB creates an Inkling token for the controller by default."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        p0_creatures = _get_battlefield_creatures(game, 0)
        inkling_tokens = [c for c in p0_creatures if "Inkling" in getattr(c, "subtypes", set())]
        assert len(inkling_tokens) == 1

    def test_inkling_token_is_1_1(self):
        """The Inkling token is a 1/1."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        p0_creatures = _get_battlefield_creatures(game, 0)
        inkling = next(c for c in p0_creatures if "Inkling" in getattr(c, "subtypes", set()))
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1

    def test_inkling_token_has_flying(self):
        """The Inkling token has flying."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        p0_creatures = _get_battlefield_creatures(game, 0)
        inkling = next(c for c in p0_creatures if "Inkling" in getattr(c, "subtypes", set()))
        assert Keyword.FLYING in inkling.keywords

    def test_inkling_token_is_creature(self):
        """The Inkling token has CREATURE card type."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        p0_creatures = _get_battlefield_creatures(game, 0)
        inkling = next(c for c in p0_creatures if "Inkling" in getattr(c, "subtypes", set()))
        assert CardType.CREATURE in inkling.card_types

    def test_etb_can_target_opponent_for_token(self):
        """The ETB trigger can target an opponent to create the Inkling token."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[1])

        p1_creatures = _get_battlefield_creatures(game, 1)
        inkling_tokens = [c for c in p1_creatures if "Inkling" in getattr(c, "subtypes", set())]
        assert len(inkling_tokens) == 1

    def test_token_is_marked_as_token(self):
        """The Inkling is marked as a token object."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        p0_creatures = _get_battlefield_creatures(game, 0)
        inkling = next(c for c in p0_creatures if "Inkling" in getattr(c, "subtypes", set()))
        assert getattr(inkling, "is_token", False) is True


# ---------------------------------------------------------------------------
# Prepared condition checks
# ---------------------------------------------------------------------------

class TestPreparedCondition:
    def test_becomes_prepared_when_opponent_has_more_creatures(self):
        """Becomes prepared if opponent controls more creatures after ETB."""
        game = create_game()
        # Opponent has 2 creatures; controller has just emeritus + token (2) after entry
        # Wait: opponent 2 > controller 2 is False. Let's use 3 vs 2.
        opp_creature1 = Creature(name="Bear1", base_power=2, base_toughness=2)
        opp_creature2 = Creature(name="Bear2", base_power=2, base_toughness=2)
        opp_creature3 = Creature(name="Bear3", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_creature1, opp_creature2, opp_creature3])

        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        # Token goes to controller (p0), making 2 creatures; opponent has 3 → prepared
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        assert emeritus.is_prepared is True

    def test_not_prepared_when_equal_creatures(self):
        """Does NOT become prepared when controller has equal creature count."""
        game = create_game()
        # Controller: emeritus + inkling = 2 after ETB
        # Opponent: 2 creatures → equal → not prepared
        opp_creature1 = Creature(name="OppBear1", base_power=2, base_toughness=2)
        opp_creature2 = Creature(name="OppBear2", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp_creature1, opp_creature2])

        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        # p0 has 2 (emeritus + inkling), p1 has 2 → not prepared
        assert emeritus.is_prepared is False

    def test_not_prepared_when_controller_has_more_creatures(self):
        """Does NOT become prepared when controller controls more creatures."""
        game = create_game()
        controller_bear1 = Creature(name="MyBear1", base_power=2, base_toughness=2)
        controller_bear2 = Creature(name="MyBear2", base_power=2, base_toughness=2)
        opp_creature = Creature(name="OppBear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[controller_bear1, controller_bear2])
        set_board_state(game, 1, battlefield=[opp_creature])

        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])
        # p0: 2 bears + emeritus + inkling = 4; p1: 1 → not prepared

        assert emeritus.is_prepared is False

    def test_not_prepared_when_opponent_has_no_creatures(self):
        """Does NOT become prepared when opponent controls no creatures."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        # p0: emeritus + inkling = 2; p1: 0 → p0 has more → not prepared
        assert emeritus.is_prepared is False

    def test_becomes_prepared_opponent_more_even_with_inkling_on_opponent_side(self):
        """Token given to opponent doesn't break the count — prepared check uses controller's count."""
        game = create_game()
        # Opponent has 3 creatures; token goes to opponent (+1 = 4); controller has only emeritus (1)
        opp1 = Creature(name="Opp1", base_power=2, base_toughness=2)
        opp2 = Creature(name="Opp2", base_power=2, base_toughness=2)
        opp3 = Creature(name="Opp3", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp1, opp2, opp3])

        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        # Token goes to opponent, making them have 4 vs controller's 1 → prepared
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[1])

        assert emeritus.is_prepared is True


# ---------------------------------------------------------------------------
# Swords to Plowshares (prepared spell)
# ---------------------------------------------------------------------------

class TestSwordsToPlowshares:
    def test_prepared_can_cast_swords_to_plowshares(self):
        """While prepared, casting STP exiles target creature."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = True
        set_board_state(game, 0, battlefield=[emeritus])

        target = Creature(name="Target", base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target])

        emeritus.cast_swords_to_plowshares(game, target)

        exile_zone = game.get_exile(game.players[1])
        assert exile_zone.contains(target)

    def test_swords_to_plowshares_gives_life_equal_to_power(self):
        """Target creature's controller gains life equal to its power."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = True
        set_board_state(game, 0, battlefield=[emeritus])

        target = Creature(name="BigBear", base_power=5, base_toughness=5)
        set_board_state(game, 1, battlefield=[target], life=20)

        emeritus.cast_swords_to_plowshares(game, target)

        assert game.players[1].life == 25  # 20 + 5

    def test_casting_swords_to_plowshares_unprepares_creature(self):
        """After casting the prepared spell, the creature becomes unprepared."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = True
        set_board_state(game, 0, battlefield=[emeritus])

        target = Creature(name="Target", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])

        emeritus.cast_swords_to_plowshares(game, target)

        assert emeritus.is_prepared is False

    def test_cannot_cast_when_not_prepared(self):
        """When not prepared, cast_swords_to_plowshares is a no-op."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = False
        set_board_state(game, 0, battlefield=[emeritus])

        target = Creature(name="Target", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target], life=20)

        emeritus.cast_swords_to_plowshares(game, target)

        p1_creatures = _get_battlefield_creatures(game, 1)
        assert target in p1_creatures
        assert game.players[1].life == 20

    def test_swords_to_plowshares_removes_from_battlefield(self):
        """After STP, the exiled creature is no longer on the battlefield."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = True
        set_board_state(game, 0, battlefield=[emeritus])

        target = Creature(name="Victim", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[target])

        emeritus.cast_swords_to_plowshares(game, target)

        p1_creatures = _get_battlefield_creatures(game, 1)
        assert target not in p1_creatures

    def test_swords_to_plowshares_target_controller_gains_life(self):
        """Life gain goes to the exiled creature's controller, not the caster."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = True
        set_board_state(game, 0, battlefield=[emeritus], life=20)

        target = Creature(name="Target", base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[target], life=20)

        emeritus.cast_swords_to_plowshares(game, target)

        assert game.players[1].life == 23  # target controller gains
        assert game.players[0].life == 20  # caster unchanged

    def test_swords_to_plowshares_zero_power_no_life_gain(self):
        """Exiling a 0-power creature grants 0 life."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = True
        set_board_state(game, 0, battlefield=[emeritus])

        target = Creature(name="WeakCreature", base_power=0, base_toughness=1)
        set_board_state(game, 1, battlefield=[target], life=20)

        emeritus.cast_swords_to_plowshares(game, target)

        assert game.players[1].life == 20

    def test_swords_to_plowshares_can_target_own_creature(self):
        """STP can target your own creature (controller's creature)."""
        game = create_game()
        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        emeritus.is_prepared = True

        target = Creature(name="OwnBear", base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[emeritus, target], life=20)

        emeritus.cast_swords_to_plowshares(game, target)

        # Controller gains 3 life, target is exiled
        assert game.players[0].life == 23
        exile_zone = game.get_exile(game.players[0])
        assert exile_zone.contains(target)


# ---------------------------------------------------------------------------
# Integration: full ETB → prepared → cast sequence
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_sequence_etb_prepared_cast(self):
        """Full flow: ETB creates token, creature becomes prepared, cast STP."""
        game = create_game()

        # Opponent has 3 creatures; controller will have emeritus + inkling (2) → prepared
        opp1 = Creature(name="Opp1", base_power=2, base_toughness=2)
        opp2 = Creature(name="Opp2", base_power=2, base_toughness=2)
        opp3 = Creature(name="Opp3", base_power=4, base_toughness=4)
        set_board_state(game, 1, battlefield=[opp1, opp2, opp3], life=20)

        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])

        assert emeritus.is_prepared is True

        emeritus.cast_swords_to_plowshares(game, opp3)

        assert emeritus.is_prepared is False
        exile_zone = game.get_exile(game.players[1])
        assert exile_zone.contains(opp3)
        assert game.players[1].life == 24  # 20 + 4

    def test_prepared_only_once_per_entry(self):
        """prepared flag starts False; ETB sets it; STP clears it."""
        game = create_game()
        opp1 = Creature(name="Opp1", base_power=2, base_toughness=2)
        opp2 = Creature(name="Opp2", base_power=2, base_toughness=2)
        opp3 = Creature(name="Opp3", base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[opp1, opp2, opp3])

        emeritus = EmeritusOfTruce(owner=game.players[0], controller=game.players[0])
        assert emeritus.is_prepared is False

        _put_on_battlefield(game, 0, emeritus, token_target=game.players[0])
        assert emeritus.is_prepared is True

        # Cast STP to use and clear the prepared state
        emeritus.cast_swords_to_plowshares(game, opp1)
        assert emeritus.is_prepared is False
