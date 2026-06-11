"""Tests for SOS 180 — Colorstorm Stallion."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_180.card_impl import ColorstormStallion
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import SpellCastTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


def _token_permanents(game: object, player: object) -> list[object]:
    return [
        permanent
        for permanent in game.get_battlefield(player).get_all()
        if getattr(permanent, "is_token", False)
    ]


class CreatureTargetingTestInstant(Instant):
    """Simple instant used to exercise ward handling."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Creature Targeting Test Spell")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]


class CheapTestInstant(Instant):
    """Simple instant used to exercise Opus triggers."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Cheap Test Instant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)


class FiveManaTestSorcery(Sorcery):
    """Simple sorcery used to exercise the five-mana Opus threshold."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Five-Mana Test Sorcery")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        super().__init__(**kwargs)


class TestColorstormStallionProperties:
    """Static card data should match the SOS 180 spec."""

    def test_is_elemental_horse_creature_with_ward_and_haste(self) -> None:
        card = ColorstormStallion(owner=None)

        assert isinstance(card, Creature)
        assert "Elemental" in card.subtypes
        assert "Horse" in card.subtypes
        assert Keyword.WARD in card.keywords
        assert Keyword.HASTE in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = ColorstormStallion(owner=None)

        assert card.name == "Colorstorm Stallion"
        assert card.mana_cost == ManaCost.parse("{1}{U}{R}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestColorstormStallionWard:
    """Colorstorm Stallion should enforce Ward {1}."""

    def test_opponents_targeting_spell_is_countered_when_they_do_not_pay_ward(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ColorstormStallion(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, hand=[spell], mana={ManaType.WHITE: 1})
        p2._script.append(card)

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "countered"
        assert game.get_graveyard(p2).contains(spell)
        assert game.stack.is_empty()

    def test_opponent_may_pay_ward_to_keep_their_spell_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = ColorstormStallion(owner=p1, controller=p1)
        spell = CreatureTargetingTestInstant(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[card])
        set_board_state(
            game,
            1,
            hand=[spell],
            mana={ManaType.WHITE: 1, ManaType.COLORLESS: 1},
        )
        p2._script.extend([card, True])

        cast_spell_paid(game, p2, spell)

        assert len(game.stack) == 2
        assert game.stack.peek().source is card

        resolve_top(game)

        assert getattr(spell, "last_ward_outcome", None) == "paid"
        assert len(game.stack) == 1
        assert game.stack.peek().source is spell
        assert p2.mana_pool.total() == 0


class TestColorstormStallionOpus:
    """Colorstorm Stallion should pump itself and copy itself off larger spells."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ColorstormStallion(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is SpellCastTriggeredEvent

    def test_casting_an_instant_gives_plus_one_plus_one_until_end_of_turn_without_creating_a_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ColorstormStallion(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)

        assert len(game.stack) == 2

        resolve_top(game)

        assert card.power == 4
        assert card.toughness == 4
        assert _token_permanents(game, p1) == []

    def test_granted_plus_one_plus_one_expires_at_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ColorstormStallion(owner=p1, controller=p1)
        spell = CheapTestInstant(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 1})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)
        assert card.power == 4
        assert card.toughness == 4

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert card.power == 3
        assert card.toughness == 3

    def test_five_or_more_mana_spell_creates_a_token_copy_while_leaving_the_original_temporarily_pumped(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ColorstormStallion(owner=p1, controller=p1)
        spell = FiveManaTestSorcery(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[card], hand=[spell], mana={ManaType.RED: 5})
        card.register_triggers(game)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert card.power == 4
        assert card.toughness == 4
        tokens = _token_permanents(game, p1)
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert token is not card
        assert token.name == "Colorstorm Stallion"
        assert "Elemental" in token.subtypes
        assert "Horse" in token.subtypes
        assert Keyword.WARD in token.keywords
        assert Keyword.HASTE in token.keywords
        assert token.power == 3
        assert token.toughness == 3

    def test_casting_a_creature_spell_does_not_trigger_opus(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = ColorstormStallion(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Practice Performer",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )

        set_board_state(
            game,
            0,
            battlefield=[card],
            hand=[creature_spell],
            mana={ManaType.RED: 2},
        )
        card.register_triggers(game)

        cast_spell_paid(game, p1, creature_spell)

        assert len(game.stack) == 1
        assert game.stack.peek().source is creature_spell

