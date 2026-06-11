"""Tests for Silverquill, the Disputant (sos_226)."""

from __future__ import annotations

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Phase, Zone
from test_utils import _resolve_top_of_stack, create_game, set_board_state


def _put_on_battlefield(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.BATTLEFIELD].add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)


def _cast_instant(game, player_index, spell, pre_script=None):
    """Place spell in hand, give 2 colorless mana, cast it, resolve stack."""
    from engine.casting import cast_spell as engine_cast_spell
    p = game.players[player_index]
    set_board_state(game, player_index, hand=[spell], mana={ManaType.COLORLESS: 2})
    game.phase = Phase.PRECOMBAT_MAIN
    game.active_player_index = player_index
    if pre_script:
        for choice in reversed(pre_script):
            p._script.appendleft(choice)
    engine_cast_spell(game, p, spell)
    _resolve_top_of_stack(game)


class TestSilverquillProperties:
    def test_name(self) -> None:
        assert SilverquillTheDisputant().name == "Silverquill, the Disputant"

    def test_keywords(self) -> None:
        sv = SilverquillTheDisputant()
        assert Keyword.FLYING in sv.keywords
        assert Keyword.VIGILANCE in sv.keywords

    def test_stats(self) -> None:
        sv = SilverquillTheDisputant()
        assert sv.base_power == 4
        assert sv.base_toughness == 4


class TestCasualtyTrigger:
    def test_copy_when_creature_sacrificed(self) -> None:
        """Casting an instant while Silverquill is out; sacrifice a 1/1 → copy resolves."""
        game = create_game()
        p1 = game.players[0]

        sv = SilverquillTheDisputant()
        _put_on_battlefield(game, 0, sv)

        fodder = Creature(name="Fodder", base_power=1, base_toughness=1)
        _put_on_battlefield(game, 0, fodder)

        class GainLife(Instant):
            def on_resolve(self_inner, game_inner):
                p1.life += 3

        spell = GainLife(name="GainLife", mana_cost=ManaCost.parse("{1}"))
        spell.owner = p1
        spell.controller = p1

        # Script: sacrifice fodder (pops first during trigger resolution)
        _cast_instant(game, 0, spell, pre_script=[fodder])

        # Two resolutions: copy gains 3, original gains 3 → total +6
        assert p1.life == 26  # 20 + 6

    def test_no_copy_if_no_eligible_creature(self) -> None:
        """Casting an instant with no power>=1 creatures → no sacrifice, no copy."""
        game = create_game()
        p1 = game.players[0]

        sv = SilverquillTheDisputant()
        _put_on_battlefield(game, 0, sv)

        # Put a 0/1 — power 0, not eligible for Casualty 1
        weak = Creature(name="Weak", base_power=0, base_toughness=1)
        _put_on_battlefield(game, 0, weak)

        class GainLife(Instant):
            def on_resolve(self_inner, game_inner):
                p1.life += 3

        spell = GainLife(name="GainLife2", mana_cost=ManaCost.parse("{1}"))
        spell.owner = p1
        spell.controller = p1

        _cast_instant(game, 0, spell)

        # Only original resolves → +3
        assert p1.life == 23

    def test_no_copy_if_decline_sacrifice(self) -> None:
        """Player scripts None (decline) → no sacrifice, no copy."""
        game = create_game()
        p1 = game.players[0]

        sv = SilverquillTheDisputant()
        _put_on_battlefield(game, 0, sv)

        fodder = Creature(name="Fodder2", base_power=2, base_toughness=2)
        _put_on_battlefield(game, 0, fodder)

        class GainLife(Instant):
            def on_resolve(self_inner, game_inner):
                p1.life += 3

        spell = GainLife(name="GainLife3", mana_cost=ManaCost.parse("{1}"))
        spell.owner = p1
        spell.controller = p1

        # Script None = decline sacrifice
        _cast_instant(game, 0, spell, pre_script=[None])

        # Only original resolves → +3
        assert p1.life == 23
        # Fodder untouched
        assert game.get_battlefield(p1).contains(fodder)

    def test_creature_goes_to_graveyard_after_sacrifice(self) -> None:
        """Sacrificed creature lands in graveyard."""
        game = create_game()
        p1 = game.players[0]

        sv = SilverquillTheDisputant()
        _put_on_battlefield(game, 0, sv)

        fodder = Creature(name="Fodder3", base_power=1, base_toughness=1)
        _put_on_battlefield(game, 0, fodder)

        class Noop(Instant):
            def on_resolve(self_inner, game_inner):
                pass

        spell = Noop(name="Noop", mana_cost=ManaCost.parse("{1}"))
        spell.owner = p1
        spell.controller = p1

        _cast_instant(game, 0, spell, pre_script=[fodder])

        # Fodder sacrificed → in graveyard
        assert not game.get_battlefield(p1).contains(fodder)
        assert game.get_graveyard(p1).contains(fodder)

    def test_creature_spells_do_not_trigger(self) -> None:
        """Casting a creature does not trigger Casualty 1."""
        from engine.casting import cast_spell as engine_cast_spell

        game = create_game()
        p1 = game.players[0]

        sv = SilverquillTheDisputant()
        _put_on_battlefield(game, 0, sv)

        fodder = Creature(name="Fodder4", base_power=1, base_toughness=1)
        _put_on_battlefield(game, 0, fodder)

        creature_spell = Creature(
            name="Vanilla", base_power=2, base_toughness=2,
            mana_cost=ManaCost.parse("{2}")
        )
        creature_spell.owner = p1
        creature_spell.controller = p1
        set_board_state(game, 0, hand=[creature_spell], mana={ManaType.COLORLESS: 2})
        game.phase = Phase.PRECOMBAT_MAIN
        game.active_player_index = 0

        engine_cast_spell(game, p1, creature_spell)
        _resolve_top_of_stack(game)

        # Fodder untouched (no casualty triggered)
        assert game.get_battlefield(p1).contains(fodder)
