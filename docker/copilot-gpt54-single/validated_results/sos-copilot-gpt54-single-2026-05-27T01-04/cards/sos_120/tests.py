"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


class TrackingInstant(Instant):
    """Simple spell used to verify free-cast resolution from exile."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Tracking Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{R}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game) -> None:
        self.resolved = True


def _set_library(player, cards_bottom_to_top: list) -> None:
    """Replace *player*'s library with the provided bottom-to-top order."""
    library = player.zones[Zone.LIBRARY]
    for card in library.get_all():
        library.remove(card)
    for card in cards_bottom_to_top:
        card.owner = player
        card.controller = player
        library.add(card)


def _advance_to_next_precombat_main(game, player) -> None:
    """Advance until *player* is active in a precombat main phase."""
    for _ in range(30):
        game.advance_phase()
        if (
            game.active_player is player
            and game.phase == Phase.PRECOMBAT_MAIN
            and game.step is None
        ):
            return
    raise AssertionError("Did not reach the requested player's next precombat main phase")


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_a_lesson_sorcery_named_improvisation_capstone(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes

    def test_has_the_expected_mana_cost_and_rules_text(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert card.rules_text == (
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)"
        )


class TestImprovisationCapstoneResolution:
    """Its first resolution should exile up to the four-mana-value threshold."""

    def test_exiles_cards_until_total_mana_value_four_or_greater_and_stops(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        one_mv = Instant(name="One-Mana Spell", mana_cost=ManaCost.parse("{R}"))
        zero_mv = Land(name="Campus")
        three_mv = Sorcery(name="Three-Mana Spell", mana_cost=ManaCost.parse("{2}{R}"))
        untouched = Instant(name="Untouched Spell", mana_cost=ManaCost.parse("{1}{R}"))

        _set_library(p1, [untouched, three_mv, zero_mv, one_mv])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert p1.zones[Zone.EXILE].contains(one_mv)
        assert p1.zones[Zone.EXILE].contains(zero_mv)
        assert p1.zones[Zone.EXILE].contains(three_mv)
        assert p1.zones[Zone.EXILE].contains(spell)
        assert p1.zones[Zone.LIBRARY].contains(untouched)
        assert not p1.zones[Zone.EXILE].contains(untouched)

    def test_you_may_decline_to_cast_the_exiled_spells(self) -> None:
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        exiled_spell = TrackingInstant()

        _set_library(p1, [exiled_spell])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert exiled_spell.resolved is False
        assert p1.zones[Zone.EXILE].contains(exiled_spell)
        assert not p1.zones[Zone.GRAVEYARD].contains(exiled_spell)
        assert p1.zones[Zone.EXILE].contains(spell)

    def test_can_free_cast_multiple_spells_from_among_the_exiled_cards_but_not_lands(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        free_instant = TrackingInstant(name="Free Instant", mana_cost=ManaCost.parse("{R}"))
        free_creature = Creature(
            name="Free Creature",
            mana_cost=ManaCost.parse("{2}{R}"),
            base_power=3,
            base_toughness=3,
        )
        exiled_land = Land(name="Practice Campus")

        _set_library(p1, [free_creature, exiled_land, free_instant])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert free_instant.resolved is True
        assert p1.zones[Zone.GRAVEYARD].contains(free_instant)
        assert p1.zones[Zone.BATTLEFIELD].contains(free_creature)
        assert p1.zones[Zone.EXILE].contains(exiled_land)
        assert p1.zones[Zone.EXILE].contains(spell)


class TestImprovisationCapstoneParadigm:
    """Paradigm should keep the original card in exile and offer future copies."""

    def test_paradigm_copy_is_optional_on_your_next_first_main_phase(self) -> None:
        game = create_game(scripts=([False], []))
        p1, p2 = game.players
        spell = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(spell)

        _advance_to_next_precombat_main(game, p2)
        assert game.stack.is_empty()

        _advance_to_next_precombat_main(game, p1)
        assert game.stack.is_empty()
        assert p1.zones[Zone.EXILE].contains(spell)

    def test_paradigm_casts_a_copy_from_exile_on_your_later_first_main_phase_only(self) -> None:
        game = create_game(scripts=([True, False], []))
        p1, p2 = game.players
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        future_spell = TrackingInstant(name="Future Spell", mana_cost=ManaCost.parse("{3}{R}"))

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")
        assert p1.zones[Zone.EXILE].contains(spell)

        _set_library(p1, [future_spell])

        _advance_to_next_precombat_main(game, p2)
        assert game.stack.is_empty()

        _advance_to_next_precombat_main(game, p1)
        assert len(game.stack) == 1

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source is not spell
        assert copy_obj.source.name == "Improvisation Capstone"
        assert p1.zones[Zone.EXILE].contains(spell)

        game.stack.pop().on_resolve(game)

        assert p1.zones[Zone.EXILE].contains(future_spell)
        assert future_spell.resolved is False
        assert p1.zones[Zone.EXILE].contains(spell)
