"""Tests for SOS 13 — Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from cards.sos.sos_13.card_impl import EmeritusOfTruce
from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Zone
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _creatures_on(game, player) -> list:
    return [
        obj
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    ]


def _make_bear(name: str = "Bear") -> Creature:
    return Creature(name=name, base_power=2, base_toughness=2)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

class TestEmeritusOfTruceIdentity:
    def test_name(self) -> None:
        card = EmeritusOfTruce()
        assert card.name == "Emeritus of Truce // Swords to Plowshares"

    def test_power_toughness(self) -> None:
        card = EmeritusOfTruce()
        assert card.base_power == 3
        assert card.base_toughness == 3

    def test_is_creature(self) -> None:
        card = EmeritusOfTruce()
        assert CardType.CREATURE in card.card_types

    def test_subtypes(self) -> None:
        card = EmeritusOfTruce()
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_mana_cost(self) -> None:
        card = EmeritusOfTruce()
        assert card.mana_cost == ManaCost.parse("{1}{W}{W}")

    def test_not_prepared_initially(self) -> None:
        card = EmeritusOfTruce()
        assert card._prepared is False


# ---------------------------------------------------------------------------
# ETB trigger — Inkling token creation
# ---------------------------------------------------------------------------

class TestEmeritusETBToken:
    def test_creates_inkling_token_for_controller(self) -> None:
        """ETB creates a 1/1 Inkling token for the controller by default."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])

        # Fire ETB trigger manually (simulating entering the battlefield).
        emeritus.register_triggers(game)
        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1),
        )
        # Resolve the trigger.
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        inklings = [
            c for c in _creatures_on(game, p1)
            if getattr(c, "name", "") == "Inkling"
        ]
        assert len(inklings) == 1

    def test_inkling_token_stats(self) -> None:
        """The Inkling token is 1/1 with flying."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.register_triggers(game)

        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        inkling = next(
            c for c in _creatures_on(game, p1)
            if getattr(c, "name", "") == "Inkling"
        )
        assert inkling.base_power == 1
        assert inkling.base_toughness == 1
        assert Keyword.FLYING in inkling.keywords

    def test_etb_token_goes_to_target_player(self) -> None:
        """Token goes to chosen_targets[0] if provided."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])
        emeritus.register_triggers(game)

        # Target player 2.
        emeritus.chosen_targets = [p2]

        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=p1),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

        # Token should be on p2's battlefield.
        inklings_p2 = [
            c for c in _creatures_on(game, p2)
            if getattr(c, "name", "") == "Inkling"
        ]
        assert len(inklings_p2) == 1
        # And not on p1's.
        inklings_p1 = [
            c for c in _creatures_on(game, p1)
            if getattr(c, "name", "") == "Inkling" and c is not emeritus
        ]
        assert len(inklings_p1) == 0


# ---------------------------------------------------------------------------
# Prepared condition
# ---------------------------------------------------------------------------

class TestEmeritusPreparation:
    def _fire_etb(self, game, emeritus, controller):
        """Helper: register + fire ETB and resolve trigger."""
        emeritus.register_triggers(game)
        from engine.events import EntersBattlefieldTriggeredEvent
        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=emeritus, controller=controller),
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)

    def test_becomes_prepared_when_opponent_has_more_creatures(self) -> None:
        """Becomes prepared when an opponent controls more creatures."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        # p1: just emeritus (1 creature); p2: 3 creatures
        opp_creatures = [_make_bear(f"OppBear{i}") for i in range(3)]
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=opp_creatures)

        self._fire_etb(game, emeritus, p1)
        assert emeritus._prepared is True

    def test_not_prepared_when_equal_creatures(self) -> None:
        """Not prepared when opponent controls equal number of creatures."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        # p1: emeritus + 1 bear = 2 creatures; p2: 2 bears = 2 creatures
        set_board_state(game, 0, battlefield=[emeritus, _make_bear("MyBear")])
        set_board_state(game, 1, battlefield=[_make_bear("OppBear1"), _make_bear("OppBear2")])

        self._fire_etb(game, emeritus, p1)
        assert emeritus._prepared is False

    def test_not_prepared_when_controller_has_more(self) -> None:
        """Not prepared when controller controls more creatures than opponent."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        bears = [_make_bear(f"Bear{i}") for i in range(3)]
        set_board_state(game, 0, battlefield=[emeritus] + bears)
        set_board_state(game, 1, battlefield=[])

        self._fire_etb(game, emeritus, p1)
        assert emeritus._prepared is False


# ---------------------------------------------------------------------------
# Prepared ability — Swords to Plowshares effect
# ---------------------------------------------------------------------------

class TestSwordsToPlowsharesEffect:
    def test_prepared_ability_exiles_creature(self) -> None:
        """When prepared, the ability exiles the target creature."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        target = _make_bear("Target Bear")
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[target])

        emeritus._prepared = True
        emeritus._stp_target = target

        abilities = emeritus.get_activated_abilities()
        assert len(abilities) == 1
        ability = abilities[0]

        # Activate: cost check
        assert ability.cost(game, emeritus) is True
        # Apply effect
        ability.effect(game)

        # Target should be in exile, not on battlefield
        exile_zone = target.owner.zones[Zone.EXILE]
        assert exile_zone.contains(target)
        assert not game.get_battlefield(p2).contains(target)

    def test_prepared_ability_grants_life(self) -> None:
        """Controller of the exiled creature gains life equal to its power."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        target = Creature(
            name="Big Creature",
            owner=p2,
            controller=p2,
            base_power=5,
            base_toughness=5,
        )
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[target], life=20)

        emeritus._prepared = True
        emeritus._stp_target = target

        abilities = emeritus.get_activated_abilities()
        ability = abilities[0]
        ability.cost(game, emeritus)
        ability.effect(game)

        assert p2.life == 25  # 20 + 5 (power)

    def test_prepared_ability_unprepares_after_use(self) -> None:
        """After activating the prepared ability, the creature is unprepared."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        target = _make_bear("Target")
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[target])

        emeritus._prepared = True
        emeritus._stp_target = target

        abilities = emeritus.get_activated_abilities()
        ability = abilities[0]
        ability.cost(game, emeritus)
        ability.effect(game)

        assert emeritus._prepared is False

    def test_prepared_cost_fails_when_not_prepared(self) -> None:
        """The ability's cost returns False when the creature isn't prepared."""
        game = create_game()
        p1 = game.players[0]

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[emeritus])

        assert emeritus._prepared is False
        abilities = emeritus.get_activated_abilities()
        assert abilities[0].cost(game, emeritus) is False

    def test_zero_power_creature_grants_no_life(self) -> None:
        """Exiling a 0-power creature grants 0 life (no change)."""
        game = create_game()
        p1, p2 = game.players

        emeritus = EmeritusOfTruce(owner=p1, controller=p1)
        zero_power = Creature(
            name="Memnite",
            owner=p2,
            controller=p2,
            base_power=0,
            base_toughness=1,
        )
        set_board_state(game, 0, battlefield=[emeritus])
        set_board_state(game, 1, battlefield=[zero_power], life=20)

        emeritus._prepared = True
        emeritus._stp_target = zero_power

        abilities = emeritus.get_activated_abilities()
        ability = abilities[0]
        ability.cost(game, emeritus)
        ability.effect(game)

        assert p2.life == 20  # unchanged
