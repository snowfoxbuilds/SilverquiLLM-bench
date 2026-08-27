"""Reference test for FDN 5 — Celestial Armor.

Flash Equipment. Static: equipped creature gets +2/+0 and flying. ETB: attach
to target creature you control and grant it hexproof + indestructible until end
of turn. Equip {3}{W} — a real colored equip cost. See fdn_129/tests.py for the
canonical Equipment test shape.
"""

from __future__ import annotations

from cards.fdn.fdn_5.card_impl import CelestialArmor
from engine.card import Creature, Equipment
from engine.turn import cleanup_mechanical
from engine.types import Keyword, ManaCost
from test_utils import create_game, set_board_state


def _bear(p):
    return Creature(name="Bear", base_power=2, base_toughness=2, owner=p, controller=p)


class TestCelestialArmorProperties:
    def test_static_data(self):
        armor = CelestialArmor(owner=None)
        assert armor.name == "Celestial Armor"
        assert armor.mana_cost == ManaCost.parse("{2}{W}")
        assert armor.equip_cost == ManaCost.parse("{3}{W}")  # colored, not approximated
        assert Keyword.FLASH in armor.keywords
        assert isinstance(armor, Equipment) and armor.is_equipment is True


class TestCelestialArmorBehaviour:
    def test_static_buff(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        armor = CelestialArmor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, armor])
        armor.equip(bear, game)
        assert (bear.power, bear.toughness) == (4, 2)  # +2/+0
        assert Keyword.FLYING in bear.keywords

    def test_etb_attach_grants_protection_until_eot(self):
        game = create_game()
        p1 = game.players[0]
        bear = _bear(p1)
        armor = CelestialArmor(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[bear, armor])
        armor.chosen_targets = [bear]
        armor.on_resolve(game)
        game.effect_manager.apply_all(game)

        assert armor.attached_to is bear
        assert Keyword.FLYING in bear.keywords
        assert Keyword.HEXPROOF in bear.keywords
        assert Keyword.INDESTRUCTIBLE in bear.keywords

        cleanup_mechanical(game)  # protection expires; static buff remains
        assert Keyword.HEXPROOF not in bear.keywords
        assert Keyword.INDESTRUCTIBLE not in bear.keywords
        assert Keyword.FLYING in bear.keywords
        assert bear.power == 4
