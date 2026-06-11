"""Tests for SOS 226 — Silverquill, the Disputant."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class Zap(Instant):
    """Probe instant: deal 2 damage to any target."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        from engine.types import TargetRequirement

        return [
            TargetRequirement(
                filter_fn=lambda obj: (
                    hasattr(obj, "life")
                    or CardType.CREATURE in getattr(obj, "card_types", set())
                ),
                description="any target",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or [None]
        if chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


class TestProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant(owner=None)
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert card.base_power == 4 and card.base_toughness == 4
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes


class TestCasualty:
    def test_sacrifice_copies_the_spell(self) -> None:
        """Sacrificing a bear copies Zap: 2+2 damage, bear dies, one card in gy."""
        game = create_game(scripts=([None, False], []))
        p1, p2 = game.players
        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        zap = Zap()
        set_board_state(game, 0, battlefield=[sq, bear], hand=[zap],
                        mana={ManaType.RED: 1})
        sq.register_triggers(game)
        p1._script[0] = bear  # casualty sacrifice choice
        cast_spell(game, 0, "Zap", targets=[p2])
        assert p2.life == 16  # original + copy
        assert p1.zones[Zone.GRAVEYARD].contains(bear)
        assert not game.get_battlefield(p1).contains(bear)
        # Only the real Zap card ends in the graveyard; the copy leaves none.
        zaps_in_gy = [c for c in p1.zones[Zone.GRAVEYARD].get_all()
                      if getattr(c, "name", "") == "Zap"]
        assert len(zaps_in_gy) == 1

    def test_decline_no_sacrifice_no_copy(self) -> None:
        game = create_game(scripts=([None], []))
        p1, p2 = game.players
        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, bear], hand=[Zap()],
                        mana={ManaType.RED: 1})
        sq.register_triggers(game)
        cast_spell(game, 0, "Zap", targets=[p2])
        assert p2.life == 18  # only the original
        assert game.get_battlefield(p1).contains(bear)

    def test_copy_may_choose_new_targets(self) -> None:
        """Copy retargeted at a creature instead of the player."""
        game = create_game(scripts=([None, True, None], []))
        p1, p2 = game.players
        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        ox = Creature(name="Ox", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, bear], hand=[Zap()],
                        mana={ManaType.RED: 1})
        set_board_state(game, 1, battlefield=[ox])
        sq.register_triggers(game)
        p1._script[0] = bear  # sacrifice
        p1._script[2] = ox    # new target for the copy
        cast_spell(game, 0, "Zap", targets=[p2])
        # Copy (on top) resolves first into the Ox; original still hits p2.
        assert p2.life == 18
        assert p2.zones[Zone.GRAVEYARD].contains(ox)

    def test_opponent_spells_unaffected(self) -> None:
        """p2's instant gets no casualty from p1's Silverquill."""
        game = create_game()
        p1, p2 = game.players
        sq = SilverquillTheDisputant()
        set_board_state(game, 0, battlefield=[sq])
        sq.register_triggers(game)
        set_board_state(game, 1, hand=[Zap()], mana={ManaType.RED: 1})
        cast_spell(game, 1, "Zap", targets=[p1])
        assert p1.life == 18  # exactly once; no prompts consumed

    def test_noninstant_spells_unaffected(self) -> None:
        game = create_game()
        p1 = game.players[0]
        sq = SilverquillTheDisputant()
        bear_card = Creature(name="Cheap Bear", mana_cost=ManaCost(generic=1),
                             base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq], hand=[bear_card],
                        mana={ManaType.COLORLESS: 1})
        sq.register_triggers(game)
        cast_spell(game, 0, "Cheap Bear")
        assert game.get_battlefield(p1).contains(bear_card)
