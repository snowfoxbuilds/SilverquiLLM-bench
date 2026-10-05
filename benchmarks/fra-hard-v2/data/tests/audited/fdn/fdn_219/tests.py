"""Regression test for FDN 219 — Elvish Archdruid.

The crash surface is ``register_triggers``, which builds the lord effect:
``ContinuousEffect(... sublayer=SubLayer.MODIFICATION ...)`` used a non-member
sublayer (the valid modify sublayer is ``MODIFY_PT``), passed the callable as
``apply_fn=`` (the field is ``apply``), and registered via
``effect_manager.register`` (the method is ``add``). This test drives
``register_triggers`` and asserts other Elves you control get +1/+1.
"""

from __future__ import annotations

from cards.fdn.fdn_219.card_impl import ElvishArchdruid
from engine.card import Creature, printed_class
from engine.types import ManaCost, ManaType
from test_utils import enter_permanent, set_board_state
from test_utils import scenario_game as create_game


class TestElvishArchdruidProperties:
    def test_name_and_cost(self) -> None:
        card = ElvishArchdruid(owner=None)
        assert printed_class(card) is ElvishArchdruid
        assert card.mana_cost == ManaCost.parse("{1}{G}{G}")
        assert card.subtypes == {"Elf", "Druid"}


class TestElvishArchdruidLord:
    """The previously-crashing register_triggers path."""

    def _setup(self):
        game = create_game()
        p1 = game.players[0]
        druid = ElvishArchdruid(owner=p1, controller=p1)
        elf = Creature(
            name="Llanowar Elves",
            subtypes={"Elf"},
            base_power=1,
            base_toughness=1,
            owner=p1,
            controller=p1,
        )
        nonelf = Creature(
            name="Grizzly Bears",
            subtypes={"Bear"},
            base_power=2,
            base_toughness=2,
            owner=p1,
            controller=p1,
        )
        set_board_state(game, 0, battlefield=[elf, nonelf])
        enter_permanent(game, p1, druid)
        return game, druid, elf, nonelf

    def test_other_elves_get_plus_one_plus_one(self) -> None:
        game, _druid, elf, nonelf = self._setup()
        game.effect_manager.apply_all(game)
        assert (elf.power, elf.toughness) == (2, 2)  # +1/+1 lord bonus
        assert (nonelf.power, nonelf.toughness) == (2, 2)  # non-Elf unaffected

    def test_mana_ability_adds_green_per_elf(self) -> None:
        from engine.abilities import activate_ability

        game, druid, _elf, _nonelf = self._setup()
        player = druid.controller
        druid.summoning_sick = False
        from test_utils import mana_ability_instance

        activate_ability(game, player, mana_ability_instance(game, player, druid))
        assert player.mana_pool.get(ManaType.GREEN) == 2 and game.stack.is_empty()
