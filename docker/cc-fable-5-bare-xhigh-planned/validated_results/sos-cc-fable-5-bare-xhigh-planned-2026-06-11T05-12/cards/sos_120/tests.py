"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land
from engine.stack import priority_loop
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import advance_to_phase, cast_spell, create_game, set_board_state


class Zap(Instant):
    """Probe instant {R}: deal 2 damage to any target."""

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


def _stock_library(game: Any, player_index: int, cards_top_first: list[Any]) -> None:
    """Put *cards_top_first* on top of the player's library (first = topmost)."""
    player = game.players[player_index]
    library = player.zones[Zone.LIBRARY]
    for card in reversed(cards_top_first):
        card.owner = player
        card.controller = player
        library.add(card)


def _capstone_mana() -> dict:
    return {ManaType.RED: 2, ManaType.COLORLESS: 5}


def _advance_to_p1_next_main(game: Any) -> None:
    """Advance through p2's turn into p1's next precombat main."""
    for _ in range(2):
        advance_to_phase(game, Phase.ENDING, Step.CLEANUP)
        game.advance_phase()  # wrap into the next turn
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)


class TestProperties:
    def test_static_data(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes


class TestResolution:
    def test_exiles_until_mv_4_and_casts_for_free(self) -> None:
        game = create_game()
        p1, p2 = game.players
        zap, bear = Zap(), Creature(name="Bear", mana_cost=ManaCost(generic=3),
                                    base_power=2, base_toughness=2)
        extra = Creature(name="Extra", mana_cost=ManaCost(generic=2),
                         base_power=1, base_toughness=1)
        _stock_library(game, 0, [zap, bear, extra])  # zap on top
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        p1._script.extend([bear, zap, p2])
        cast_spell(game, 0, "Improvisation Capstone")
        # 1 + 3 = 4 stops the exiling — 'extra' stays in the library.
        assert p1.zones[Zone.LIBRARY].contains(extra)
        assert game.get_battlefield(p1).contains(bear)
        assert p2.life == 18
        assert p1.zones[Zone.GRAVEYARD].contains(zap)
        # Paradigm: the Capstone itself is exiled, not binned.
        assert p1.zones[Zone.EXILE].contains(cap)
        assert not p1.zones[Zone.GRAVEYARD].contains(cap)

    def test_library_runs_out_and_lands_stay_exiled(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lands = [Land(name="Wastes A"), Land(name="Wastes B")]
        _stock_library(game, 0, list(lands))
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        cast_spell(game, 0, "Improvisation Capstone")  # no castable → no prompt
        for land in lands:
            assert p1.zones[Zone.EXILE].contains(land)
        assert len(p1.zones[Zone.LIBRARY]) == 0
        assert p1.zones[Zone.EXILE].contains(cap)

    def test_may_decline_all_casts(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", mana_cost=ManaCost(generic=4),
                        base_power=2, base_toughness=2)
        _stock_library(game, 0, [bear])
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        p1._script.extend([None])
        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(bear)
        assert not game.get_battlefield(p1).contains(bear)


class TestParadigm:
    def _resolve_first(self, game: Any) -> Any:
        """Cast and resolve the Capstone declining its free cast."""
        p1 = game.players[0]
        cap = ImprovisationCapstone()
        set_board_state(game, 0, hand=[cap], mana=_capstone_mana())
        p1._script.extend([None])
        cast_spell(game, 0, "Improvisation Capstone")
        return cap

    def test_copy_cast_at_first_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear1 = Creature(name="Bear One", mana_cost=ManaCost(generic=4),
                         base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear Two", mana_cost=ManaCost(generic=4),
                         base_power=2, base_toughness=2)
        _stock_library(game, 0, [bear1, bear2])
        cap = self._resolve_first(game)  # exiles bear1, declines
        _advance_to_p1_next_main(game)
        p1._script.extend(["pass", True, "pass", bear2, "pass"])
        p2._script.extend(["pass", "pass", "pass"])
        priority_loop(game)
        assert game.get_battlefield(p1).contains(bear2)
        assert p1.zones[Zone.EXILE].contains(cap)      # original stays exiled
        assert p1.zones[Zone.EXILE].contains(bear1)    # declined card stays
        # "First resolve" guard — the copy resolving must not re-register.
        assert len(game.trigger_manager.get_triggers_for_source(cap)) == 1

    def test_paradigm_cast_may_be_declined(self) -> None:
        game = create_game()
        p1, p2 = game.players
        bear1 = Creature(name="Bear One", mana_cost=ManaCost(generic=4),
                         base_power=2, base_toughness=2)
        _stock_library(game, 0, [bear1])
        cap = self._resolve_first(game)
        _advance_to_p1_next_main(game)
        p1._script.extend(["pass", False])
        p2._script.extend(["pass"])
        priority_loop(game)
        assert game.stack.is_empty()
        assert p1.zones[Zone.EXILE].contains(cap)
