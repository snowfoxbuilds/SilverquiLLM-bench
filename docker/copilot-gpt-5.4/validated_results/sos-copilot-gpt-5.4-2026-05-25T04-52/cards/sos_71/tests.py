"""Tests for SOS 71 — Wisdom of Ages."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_71.card_impl import WisdomOfAges
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.turn import _do_cleanup_step
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestWisdomOfAgesProperties:
    """Static card data should match the SOS 71 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(WisdomOfAges(owner=None), Sorcery)

    def test_name_and_mana_cost(self) -> None:
        card = WisdomOfAges(owner=None)
        assert card.name == "Wisdom of Ages"
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}{U}")


class TestWisdomOfAgesResolution:
    """Wisdom of Ages should recover spells, remove hand-size limits, and exile itself."""

    def test_on_resolve_returns_all_instant_and_sorcery_cards_from_your_graveyard_to_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        instant_card = Instant(name="Recovered Insight", owner=p1, controller=p1)
        sorcery_card = Sorcery(name="Recovered Thesis", owner=p1, controller=p1)
        creature_card = Creature(
            name="Stays Buried",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, graveyard=[instant_card, sorcery_card, creature_card])

        WisdomOfAges(owner=p1, controller=p1).on_resolve(game)

        assert game.get_hand(p1).contains(instant_card)
        assert game.get_hand(p1).contains(sorcery_card)
        assert not game.get_graveyard(p1).contains(instant_card)
        assert not game.get_graveyard(p1).contains(sorcery_card)
        assert game.get_graveyard(p1).contains(creature_card)

    def test_paid_cast_exiles_itself_on_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = WisdomOfAges(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={
                ManaType.BLUE: 3,
                ManaType.COLORLESS: 4,
            },
        )

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert not game.get_graveyard(p1).contains(spell)

    def test_resolving_spell_keeps_you_from_discarding_during_cleanup_for_the_rest_of_the_game(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = WisdomOfAges(owner=p1, controller=p1)
        recovered_spell = Instant(name="Recovered Insight", owner=p1, controller=p1)
        extra_hand_cards = [
            CardImpl(name=f"Hand Card {idx}", owner=p1, controller=p1)
            for idx in range(7)
        ]
        set_board_state(
            game,
            0,
            hand=[spell, *extra_hand_cards],
            graveyard=[recovered_spell],
            mana={
                ManaType.BLUE: 3,
                ManaType.COLORLESS: 4,
            },
        )

        cast_spell_paid(game, p1, spell)
        resolve_top(game)
        _do_cleanup_step(game)

        assert len(game.get_hand(p1).get_all()) == 8
        assert game.get_hand(p1).contains(recovered_spell)
        assert game.get_graveyard(p1).get_all() == []

