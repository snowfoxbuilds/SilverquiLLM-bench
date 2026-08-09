"""Reference test for FDN 86 — Fiery Annihilation.

Exercises `TargetRequirement.optional`: "up to one target Equipment" is a
declinable second target, so the spell stays castable when no Equipment is on
the battlefield (the pre-optional version raised CastingError there).
"""

from __future__ import annotations

from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from engine.card import Artifact, Creature
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


def _bear(p, name="Bear", tough=2):
    return Creature(name=name, base_power=2, base_toughness=tough, owner=p, controller=p)


class TestFieryAnnihilationProperties:
    def test_static_data(self):
        fa = FieryAnnihilation(owner=None)
        assert fa.name == "Fiery Annihilation"
        assert fa.mana_cost == ManaCost.parse("{2}{R}")

    def test_equipment_spec_is_optional(self):
        fa = FieryAnnihilation(owner=None)
        specs = fa.get_targets(None)
        assert len(specs) == 2
        assert specs[0].optional is False   # target creature — required
        assert specs[1].optional is True    # up to one Equipment — optional


class TestFieryAnnihilation:
    def test_castable_with_no_equipment_deals_damage(self):
        """No Equipment on the battlefield: the spell still casts (optional
        second target skipped) and deals 5 damage to the creature."""
        game = create_game()
        p1, p2 = game.players
        bear = _bear(p2)
        set_board_state(game, 1, battlefield=[bear])
        fa = FieryAnnihilation(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[fa], mana={ManaType.RED: 3})
        cast_spell(game, 0, "Fiery Annihilation", targets=[bear])
        assert not game.get_battlefield(p2).contains(bear)   # 5 dmg killed 2/2

    def test_exiles_targeted_equipment(self):
        """With an attached Equipment targeted, it is exiled."""
        game = create_game()
        p1, p2 = game.players
        bear = _bear(p2, tough=6)   # survives 5 damage so we can see the exile
        gear = Artifact(name="Gear", subtypes={"Equipment"}, owner=p2, controller=p2)
        gear.attached_to = bear
        set_board_state(game, 1, battlefield=[bear, gear])
        fa = FieryAnnihilation(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[fa], mana={ManaType.RED: 3})
        cast_spell(game, 0, "Fiery Annihilation", targets=[bear, gear])
        assert game.get_exile(p2).contains(gear) or not game.get_battlefield(p2).contains(gear)
