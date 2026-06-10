"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.events import EndStepTriggeredEvent
from engine.types import CardType, ManaCost, ManaType
from test_utils import create_game, set_board_state, cast_spell


class MarkerInstant(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Probe")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def _mana_ability(gh, p, index):
    ma = gh.get_mana_abilities()[index]
    return ActivatedAbilityInstance(source=gh, controller=p, cost=ma.cost,
                                    effect=ma.mana_produced, is_mana_ability=True)


def _activate5(gh, p):
    aa = gh.get_activated_abilities()[0]
    return ActivatedAbilityInstance(source=gh, controller=p, cost=aa.cost,
                                    effect=aa.effect, is_mana_ability=False)


def _drain(game):
    while not game.stack.is_empty():
        game.stack.pop().on_resolve(game)


class TestProperties:
    def test_is_land(self):
        gh = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(gh, Land)
        assert gh.name == "Great Hall of the Biblioplex"
        assert CardType.LAND in gh.card_types
        assert gh.can_cast(create_game()) is False


class TestManaAbilities:
    def test_colorless(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh])
        activate_ability(game, p0, _mana_ability(gh, p0, 0))
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert gh.is_tapped is True

    def test_restricted_color_pays_only_instant_sorcery(self):
        game = create_game(scripts=([ManaType.BLUE], []))
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], life=20)
        activate_ability(game, p0, _mana_ability(gh, p0, 1))
        assert p0.mana_pool.get(ManaType.BLUE) == 1
        assert p0.life == 19  # paid 1 life

        # A creature spell cannot be paid by the restricted mana.
        bear = Creature(name="Bear", base_power=1, base_toughness=1,
                        mana_cost=ManaCost.parse("{U}"))
        set_board_state(game, 0, hand=[bear])
        raised = False
        try:
            cast_spell(game, 0, "Bear")
        except Exception:
            raised = True
        assert raised
        assert "Bear" not in [c.name for c in game.get_battlefield(p0).get_all()]

    def test_restricted_color_can_cast_instant(self):
        game = create_game(scripts=([ManaType.BLUE], []))
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], hand=[MarkerInstant(owner=None)])
        activate_ability(game, p0, _mana_ability(gh, p0, 1))
        cast_spell(game, 0, "Probe")
        assert game.get_graveyard(p0).contains(
            next(c for c in game.get_graveyard(p0).get_all() if c.name == "Probe")
        )


class TestAnimation:
    def _animate(self):
        game = create_game()
        p0 = game.players[0]
        gh = GreatHallOfTheBiblioplex(owner=None)
        set_board_state(game, 0, battlefield=[gh], mana={ManaType.COLORLESS: 5})
        activate_ability(game, p0, _activate5(gh, p0))
        _drain(game)
        return game, p0, gh

    def test_becomes_2_4_wizard_still_land(self):
        game, p0, gh = self._animate()
        assert CardType.CREATURE in gh.card_types
        assert CardType.LAND in gh.card_types  # still a land
        assert "Wizard" in gh.subtypes
        assert gh.power == 2 and gh.toughness == 4
        assert p0.mana_pool.get(ManaType.COLORLESS) == 0  # paid {5}

    def test_pump_on_cast_stacks(self):
        game, p0, gh = self._animate()
        set_board_state(game, 0, hand=[MarkerInstant(owner=None)],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert gh.power == 3
        set_board_state(game, 0, hand=[MarkerInstant(owner=None)],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert gh.power == 4

    def test_pump_resets_at_end_step(self):
        game, p0, gh = self._animate()
        set_board_state(game, 0, hand=[MarkerInstant(owner=None)],
                        mana={ManaType.BLUE: 1})
        cast_spell(game, 0, "Probe")
        assert gh.power == 3
        # Fire the real end-step event (as turn.py does) and resolve.
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p0))
        _drain(game)
        assert gh.power == 2

    def test_animation_only_once(self):
        game, p0, gh = self._animate()
        # Already a creature → second activation cost shouldn't even be payable
        # without mana, and the effect is gated.
        gh.power = 99  # sentinel; animating again must NOT reset to 2
        set_board_state(game, 0, mana={ManaType.COLORLESS: 5})
        activate_ability(game, p0, _activate5(gh, p0))
        _drain(game)
        assert gh.power == 99
