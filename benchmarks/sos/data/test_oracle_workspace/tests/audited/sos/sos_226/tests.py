"""Audited tests for Silverquill, the Disputant (sos_226).

Oracle: {2}{W}{B} 4/4 Legendary Creature — Elder Dragon.
  Flying, vigilance
  Each instant and sorcery spell you cast has casualty 1.  (As you cast that
  spell, you may sacrifice a creature with power 1 or greater.  When you do,
  copy the spell and you may choose new targets for the copy.)

Simulation-only shape (AUDITED-TEST-API.md): casualty is a granted keyword
exercised indirectly — the subject instant is cast via a ``CastSpell``
directive, the engine raises the "sacrifice which creature?" prompt through
the public choice API, and the answer comes from the choice script
(Channel 2).  The doubled resolution is asserted through the doubled
observable result (the fixture spell gains its controller 2 life, so paying
casualty yields +4).  The oracle copies the spell with the *same* targets, so
retargeting is not asserted.

Tests:
  1. test_card_identity
  2. test_casualty_paid_copies_the_spell
  3. test_casualty_may_be_declined
  4. test_zero_power_creature_is_not_a_legal_casualty_sacrifice
  5. test_no_casualty_on_creature_spells
  6. test_no_casualty_without_the_granter
"""

from __future__ import annotations

from card_impl import SilverquillTheDisputant

from engine.card import Creature, Instant
from engine.types import CardType, ManaCost, ManaType, Phase, Supertype, Zone
from test_utils import (
    CastSpell,
    DeterministicPlayer,
    advance_to_phase,
    assert_in_zone,
    assert_life_total,
    assert_stack,
    assert_stack_empty,
    assert_zone_count,
    assert_zone_exact,
    create_game,
    no_op,
    perform_action,
    priority_loop,
    set_board_state,
    set_player,
)

_NAME = "Silverquill, the Disputant"


class SoothingWords(Instant):
    """Fixture card — {W} instant: you gain 2 life (untargeted).

    Hook bodies are card-implementation code, exempt from the API
    conformance scan.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Soothing Words")
        kwargs.setdefault("mana_cost", ManaCost(pips={ManaType.WHITE: 1}))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


def _fodder(name: str = "Fodder") -> Creature:
    return Creature(name=name, base_power=1, base_toughness=1)


def _cast_soothing_words(game, *, battlefield, choices) -> None:
    """Cast the fixture instant with the given board and choice script."""
    advance_to_phase(game, Phase.PRECOMBAT_MAIN)
    set_board_state(
        game, 0,
        battlefield=battlefield,
        hand=[SoothingWords()],
        mana={ManaType.WHITE: 1},
    )
    set_player(game, 0, DeterministicPlayer("P0", script=[
        perform_action(CastSpell("Soothing Words")),
        no_op(),
        no_op(),
    ], choices=choices))
    set_player(game, 1, DeterministicPlayer("P1", script=[
        no_op(),
        no_op(),
    ]))
    priority_loop(game)


class TestIdentity:
    def test_card_identity(self) -> None:
        card = SilverquillTheDisputant()
        assert card.name == _NAME
        assert card.mana_cost.generic == 2
        assert card.mana_cost.pips.get(ManaType.WHITE) == 1
        assert card.mana_cost.pips.get(ManaType.BLACK) == 1
        assert card.mana_cost.cmc == 4
        assert CardType.CREATURE in card.card_types
        assert isinstance(card, Creature)
        assert Supertype.LEGENDARY in card.supertypes
        assert "Elder" in card.subtypes
        assert "Dragon" in card.subtypes
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestCasualty:
    def test_casualty_paid_copies_the_spell(self) -> None:
        """Sacrificing the 1/1 to casualty resolves the spell twice: the
        controller gains 4 life and the sacrificed creature is in the
        graveyard.  The copy ceases to exist — only the real card reaches
        the graveyard."""
        game = create_game()
        fodder = _fodder()
        _cast_soothing_words(
            game,
            battlefield=[SilverquillTheDisputant(), fodder],
            choices=[fodder],
        )

        assert_life_total(game, 0, 24)
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Fodder")
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Soothing Words", count=1)
        assert_zone_exact(game, 0, Zone.BATTLEFIELD, [_NAME])
        # No lingering copy: the stack drained completely.
        assert_stack(game, [])
        assert_stack_empty(game)

    def test_casualty_may_be_declined(self) -> None:
        """Declining the additional cost resolves the spell exactly once and
        sacrifices nothing."""
        game = create_game()
        fodder = _fodder()
        _cast_soothing_words(
            game,
            battlefield=[SilverquillTheDisputant(), fodder],
            choices=[None],
        )

        assert_life_total(game, 0, 22)
        assert_in_zone(game, 0, Zone.BATTLEFIELD, "Fodder")
        assert_zone_count(game, 0, Zone.GRAVEYARD, 1)  # just the spell

    def test_zero_power_creature_is_not_a_legal_casualty_sacrifice(self) -> None:
        """Casualty 1 requires power >= 1: answering the prompt with a
        0-power creature is not a legal payment — nothing is sacrificed and
        the spell resolves once."""
        game = create_game()
        wimp = Creature(name="Wimp", base_power=0, base_toughness=1)
        _cast_soothing_words(
            game,
            battlefield=[SilverquillTheDisputant(), wimp],
            choices=[wimp],
        )

        assert_life_total(game, 0, 22)
        assert_in_zone(game, 0, Zone.BATTLEFIELD, "Wimp")
        assert_in_zone(game, 0, Zone.GRAVEYARD, "Soothing Words", count=1)

    def test_no_casualty_on_creature_spells(self) -> None:
        """Only instants and sorceries gain casualty — casting a creature
        offers no sacrifice prompt (a dry choice script would fail the test
        if it did)."""
        game = create_game()
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        fodder = _fodder()
        bear = Creature(
            name="Grizzly Bears",
            base_power=2, base_toughness=2,
            mana_cost=ManaCost(generic=1),
        )
        set_board_state(
            game, 0,
            battlefield=[SilverquillTheDisputant(), fodder],
            hand=[bear],
            mana={ManaType.COLORLESS: 1},
        )
        set_player(game, 0, DeterministicPlayer("P0", script=[
            perform_action(CastSpell("Grizzly Bears")),
            no_op(),
        ]))
        set_player(game, 1, DeterministicPlayer("P1", script=[no_op()]))
        priority_loop(game)

        assert_in_zone(game, 0, Zone.BATTLEFIELD, "Grizzly Bears")
        assert_in_zone(game, 0, Zone.BATTLEFIELD, "Fodder")
        assert_zone_count(game, 0, Zone.GRAVEYARD, 0)

    def test_no_casualty_without_the_granter(self) -> None:
        """Without Silverquill on the battlefield an instant gets no casualty
        prompt and resolves once."""
        game = create_game()
        fodder = _fodder()
        _cast_soothing_words(
            game,
            battlefield=[fodder],
            choices=[],
        )

        assert_life_total(game, 0, 22)
        assert_in_zone(game, 0, Zone.BATTLEFIELD, "Fodder")
