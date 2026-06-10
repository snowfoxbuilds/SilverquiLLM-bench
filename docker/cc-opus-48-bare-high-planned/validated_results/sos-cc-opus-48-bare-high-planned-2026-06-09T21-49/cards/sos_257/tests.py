"""Tests for SOS 257 — Great Hall of the Biblioplex."""

from __future__ import annotations

from cards.sos.sos_257.card_impl import GreatHallOfTheBiblioplex
from engine.abilities import ActivatedAbilityInstance, activate_ability
from engine.card import Creature, Instant, Land
from engine.types import CardType, ManaCost, ManaType, Zone
from engine.state_based_actions import resolve_state_based_actions
from test_utils import create_game, set_board_state, cast_spell


class _Inst(Instant):
    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Blue Inst")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        pass


def _activate_mana(game, land, ctrl, index):
    ma = land.get_mana_abilities()[index]
    inst = ActivatedAbilityInstance(source=land, controller=ctrl,
                                    cost=ma.cost, effect=ma.mana_produced,
                                    is_mana_ability=True)
    activate_ability(game, ctrl, inst)


def _activate_five(game, land, ctrl):
    ab = land.get_activated_abilities()[0]
    inst = ActivatedAbilityInstance(source=land, controller=ctrl,
                                    cost=ab.cost, effect=ab.effect,
                                    is_mana_ability=False)
    activate_ability(game, ctrl, inst)
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


class TestProperties:
    def test_is_land(self):
        c = GreatHallOfTheBiblioplex(owner=None)
        assert isinstance(c, Land)
        assert CardType.LAND in c.card_types
        assert c.can_cast(None) is False


class TestManaAbilities:
    def test_tap_for_colorless(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land])
        _activate_mana(game, land, p0, 0)
        assert p0.mana_pool.get(ManaType.COLORLESS) == 1
        assert land.is_tapped is True

    def test_pay_life_for_restricted_color(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], life=20)
        p0._script.append(ManaType.BLUE)
        _activate_mana(game, land, p0, 1)
        assert p0.life == 19
        assert p0.mana_pool.get(ManaType.BLUE) == 1
        # Restricted: can pay for an instant/sorcery, not for other spells.
        assert p0.mana_pool.can_pay(ManaCost.parse("{U}"), instant_or_sorcery=True)
        assert not p0.mana_pool.can_pay(ManaCost.parse("{U}"), instant_or_sorcery=False)

    def test_restricted_mana_only_pays_instants(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        creature = Creature(name="Blue Bear", mana_cost=ManaCost.parse("{U}"),
                            base_power=1, base_toughness=1)
        inst = _Inst()
        set_board_state(game, 0, battlefield=[land], hand=[creature, inst], life=20)
        p0._script.append(ManaType.BLUE)
        _activate_mana(game, land, p0, 1)  # restricted U
        # Creature cast must fail (restricted mana can't pay it).
        try:
            cast_spell(game, 0, "Blue Bear")
        except Exception:
            pass
        assert any(getattr(c, "name", "") == "Blue Bear"
                   for c in p0.zones[Zone.HAND].get_all())
        # Instant cast succeeds with the restricted mana.
        cast_spell(game, 0, "Blue Inst")
        assert any(getattr(c, "name", "") == "Blue Inst"
                   for c in p0.zones[Zone.GRAVEYARD].get_all())


class TestAnimation:
    def test_five_animates(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land], mana={ManaType.COLORLESS: 5})
        _activate_five(game, land, p0)
        assert CardType.CREATURE in land.card_types
        assert CardType.LAND in land.card_types  # still a land
        assert "Wizard" in land.subtypes
        assert land.power == 2
        assert land.toughness == 4

    def test_pump_on_instant_cast(self):
        game = create_game()
        p0 = game.players[0]
        land = GreatHallOfTheBiblioplex(owner=p0, controller=p0)
        set_board_state(game, 0, battlefield=[land],
                        hand=[_Inst(), _Inst()],
                        mana={ManaType.COLORLESS: 5})
        _activate_five(game, land, p0)
        assert land.power == 2
        # Cast an instant → +1/+0.
        p0.mana_pool.add(ManaType.BLUE, 1)
        cast_spell(game, 0, "Blue Inst")
        assert land.power == 3
        # Second instant → stacks.
        p0.mana_pool.add(ManaType.BLUE, 1)
        cast_spell(game, 0, "Blue Inst")
        assert land.power == 4
        # End-of-turn cleanup clears the until-EOT pump.
        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)
        assert land.power == 2
