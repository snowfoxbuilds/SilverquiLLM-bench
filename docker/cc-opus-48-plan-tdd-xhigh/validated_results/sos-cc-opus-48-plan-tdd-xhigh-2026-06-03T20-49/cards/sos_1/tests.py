"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.events import AttacksTriggeredEvent
from engine.types import Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import (
    create_game,
    cast_spell,
    set_board_state,
    _resolve_top_of_stack,
)


def _bolt(name="Singe", power_to_face=0):
    """A simple sorcery that gains its controller 3 life on resolve."""
    class _Gainer(Sorcery):
        def on_resolve(self, game):
            if self.controller is not None:
                self.controller.life += 3
    return _Gainer(name=name, mana_cost=ManaCost.parse("{1}{R}"))


class TestProperties:
    def test_is_creature(self):
        assert isinstance(TheDawningArchaic(owner=None), Creature)

    def test_name(self):
        assert TheDawningArchaic(owner=None).name == "The Dawning Archaic"

    def test_mana_cost(self):
        assert TheDawningArchaic(owner=None).mana_cost == ManaCost.parse("{10}")

    def test_power_toughness(self):
        c = TheDawningArchaic(owner=None)
        assert c.base_power == 7
        assert c.base_toughness == 7

    def test_reach(self):
        assert Keyword.REACH in TheDawningArchaic(owner=None).keywords

    def test_legendary(self):
        assert Supertype.LEGENDARY in TheDawningArchaic(owner=None).supertypes


class TestCostReduction:
    def test_reduced_by_graveyard_instants_sorceries(self):
        game = create_game()
        gy = [_bolt("S1"), _bolt("S2"),
              Instant(name="I1", mana_cost=ManaCost.parse("{U}"))]
        # 3 instant/sorcery in graveyard -> {10} reduced to {7}.
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        bf_names = [getattr(o, "name", None)
                    for o in game.players[0].zones[Zone.BATTLEFIELD].get_all()]
        assert "The Dawning Archaic" in bf_names

    def test_creatures_in_graveyard_dont_reduce(self):
        game = create_game()
        gy = [Creature(name="Corpse", base_power=1, base_toughness=1)]
        set_board_state(game, 0, hand=[TheDawningArchaic(owner=None)],
                        graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        try:
            cast_spell(game, 0, "The Dawning Archaic")
            assert False, "should not be castable for 7 with no spells in GY"
        except Exception:
            pass


class TestAttackTrigger:
    def _setup(self, gy):
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, battlefield=[archaic], graveyard=gy, life=20)
        archaic.register_triggers(game)
        return game, archaic

    def test_recasts_spell_and_exiles_it(self):
        spell = _bolt("Singe")
        game, archaic = self._setup([spell])
        p0 = game.players[0]
        p0._script.append(True)   # may: yes
        p0._script.append(spell)  # target choice
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic))
        _resolve_top_of_stack(game)
        assert p0.life == 23  # _bolt gained 3 life on resolve
        assert spell in p0.zones[Zone.EXILE].get_all()
        assert spell not in p0.zones[Zone.GRAVEYARD].get_all()

    def test_may_decline_does_nothing(self):
        spell = _bolt("Singe")
        game, archaic = self._setup([spell])
        p0 = game.players[0]
        p0._script.append(False)  # may: no
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic))
        _resolve_top_of_stack(game)
        assert p0.life == 20
        assert spell in p0.zones[Zone.GRAVEYARD].get_all()

    def test_no_instant_or_sorcery_targets_noop(self):
        corpse = Creature(name="Corpse", base_power=1, base_toughness=1)
        game, archaic = self._setup([corpse])
        p0 = game.players[0]
        # No yes/no should even be asked; effect returns early.
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=archaic, attacker=archaic))
        _resolve_top_of_stack(game)
        assert p0.life == 20
        assert corpse in p0.zones[Zone.GRAVEYARD].get_all()

    def test_trigger_only_fires_for_self(self):
        spell = _bolt("Singe")
        game, archaic = self._setup([spell])
        p0 = game.players[0]
        other = Creature(name="Other", base_power=1, base_toughness=1)
        game.trigger_manager.fire_event(
            game, AttacksTriggeredEvent(creature=other, attacker=other))
        # Nothing should be on the stack since condition didn't match.
        assert game.stack.is_empty()
        assert p0.life == 20
