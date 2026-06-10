"""Tests for SOS 226 — Silverquill, the Disputant (Casualty 1)."""

from __future__ import annotations

from typing import Any

from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Supertype, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state

from cards.sos.sos_226.card_impl import SilverquillTheDisputant


class Zap(Instant):
    """Test instant: deal 2 damage to target player."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: hasattr(obj, "life"),
                description="target player",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(p1_script: list[Any]):
    """Game with Silverquill + a bear on p1's battlefield, Zap in hand."""
    game = create_game(scripts=(p1_script, []))
    sq = SilverquillTheDisputant()
    bear = Creature(name="Bear", base_power=2, base_toughness=2)
    zap = Zap()
    set_board_state(
        game, 0, battlefield=[sq, bear], hand=[zap], mana={ManaType.RED: 1}
    )
    sq.register_triggers(game)
    return game, sq, bear, zap


class TestProperties:
    def test_static_data(self) -> None:
        card = SilverquillTheDisputant()
        assert card.name == "Silverquill, the Disputant"
        assert card.mana_cost == ManaCost.parse("{2}{W}{B}")
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords
        assert Supertype.LEGENDARY in card.supertypes
        assert card.base_power == 4 and card.base_toughness == 4


class TestCasualty:
    def test_sacrifice_copies_spell(self) -> None:
        """Sacrificing the bear copies Zap → 4 total damage, bear dies."""
        game, sq, bear, zap = _setup([])
        p1, p2 = game.players
        p2_life = p2.life
        # Script: choose_card answer (the bear) — targets come via cast_spell.
        p1._script.append(bear)

        cast_spell(game, 0, "Zap", targets=[p2])

        assert p2.life == p2_life - 4
        assert p1.zones[Zone.GRAVEYARD].contains(bear)
        assert p1.zones[Zone.GRAVEYARD].contains(zap)

    def test_decline_no_copy(self) -> None:
        """Declining (None) → no sacrifice, single resolution."""
        game, sq, bear, zap = _setup([])
        p1, p2 = game.players
        p2_life = p2.life
        p1._script.append(None)

        cast_spell(game, 0, "Zap", targets=[p2])

        assert p2.life == p2_life - 2
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)

    def test_no_eligible_creature_no_prompt(self) -> None:
        """No creature with power ≥ 1 → casualty simply not taken, no prompt.

        Silverquill itself is normally eligible (power 4), so drop its power
        to 0 (keeping toughness) to reach the empty-candidates path.
        """
        game = create_game()
        sq = SilverquillTheDisputant()
        zap = Zap()
        set_board_state(
            game, 0, battlefield=[sq], hand=[zap], mana={ManaType.RED: 1}
        )
        sq.register_triggers(game)
        sq.base_power = 0
        sq.modified_power = 0  # power 0, toughness 4
        p2 = game.players[1]
        p2_life = p2.life

        # No choose_card is scripted — an unexpected prompt would raise.
        cast_spell(game, 0, "Zap", targets=[p2])

        assert p2.life == p2_life - 2
        assert game.players[0].zones[Zone.BATTLEFIELD].contains(sq)

    def test_opponent_spell_not_granted_casualty(self) -> None:
        """Opponent's spell doesn't trigger your Silverquill's casualty."""
        game = create_game()
        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[sq, bear])
        sq.register_triggers(game)
        zap = Zap()
        set_board_state(game, 1, hand=[zap], mana={ManaType.RED: 1})
        p1 = game.players[0]
        p1_life = p1.life

        cast_spell(game, 1, "Zap", targets=[p1])

        assert p1.life == p1_life - 2  # one resolution only
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)

    def test_creature_spell_not_granted_casualty(self) -> None:
        """Casting a creature spell does not trigger casualty."""
        game = create_game()
        sq = SilverquillTheDisputant()
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        wolf = Creature(name="Wolf", base_power=2, base_toughness=2,
                        mana_cost=ManaCost.parse("{1}"))
        set_board_state(game, 0, battlefield=[sq, bear], hand=[wolf],
                        mana={ManaType.COLORLESS: 1})
        sq.register_triggers(game)
        p1 = game.players[0]

        # No choose_card is scripted — an unexpected prompt would raise.
        cast_spell(game, 0, "Wolf")

        assert p1.zones[Zone.BATTLEFIELD].contains(wolf)
        assert p1.zones[Zone.BATTLEFIELD].contains(bear)
