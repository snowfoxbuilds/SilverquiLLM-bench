"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Creature, Instant, Sorcery
from engine.casting import get_cost_reduction
from engine.combat import _can_block
from engine.events import AttacksTriggeredEvent
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestSorceryFromGraveyard(Sorcery):
    """Simple spell used to verify graveyard free-casting behavior."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Borrowed Insight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        super().__init__(**kwargs)
        self.resolved = False

    def on_resolve(self, game) -> None:
        self.resolved = True
        if self.controller is not None:
            self.controller.life += 3


class TestTheDawningArchaicProperties:
    """Static card data should match the SOS 1 spec."""

    def test_is_legendary_avatar_creature_with_reach(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert isinstance(card, Creature)
        assert CardType.CREATURE in card.card_types
        assert Supertype.LEGENDARY in card.supertypes
        assert "Avatar" in card.subtypes
        assert Keyword.REACH in card.keywords

    def test_mana_cost_and_power_toughness(self) -> None:
        card = TheDawningArchaic(owner=None)
        assert card.mana_cost == ManaCost.parse("{10}")
        assert card.base_power == 7
        assert card.base_toughness == 7


class TestTheDawningArchaicCostReduction:
    """Casting cost should shrink based on instants and sorceries in your graveyard."""

    def test_cost_reduction_counts_only_your_instants_and_sorceries(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        card = TheDawningArchaic(owner=p1, controller=p1)

        your_instant = Instant(name="Zap")
        your_sorcery = Sorcery(name="Study")
        your_creature = Creature(name="Bear", base_power=2, base_toughness=2)
        opponent_instant = Instant(name="Shock")

        set_board_state(
            game,
            0,
            graveyard=[your_instant, your_sorcery, your_creature],
        )
        set_board_state(game, 1, graveyard=[opponent_instant])

        assert get_cost_reduction(game, card, p1) == 2
        assert get_cost_reduction(game, card, p2) == 1

    def test_ten_spells_in_your_graveyard_allow_zero_mana_cast(self) -> None:
        game = create_game()
        archaic = TheDawningArchaic(owner=None)
        graveyard = [Instant(name=f"Spell {n}") for n in range(10)]

        set_board_state(game, 0, hand=[archaic], graveyard=graveyard, mana={})

        cast_spell(game, 0, "The Dawning Archaic")

        battlefield = game.players[0].zones[Zone.BATTLEFIELD]
        assert battlefield.contains(archaic)


class TestTheDawningArchaicReach:
    """Reach should let The Dawning Archaic block fliers."""

    def test_can_block_a_flying_attacker(self) -> None:
        blocker = TheDawningArchaic(owner=None)
        attacker = Creature(
            name="Sky Drake",
            base_power=2,
            base_toughness=2,
            keywords=Keyword.FLYING,
        )

        assert _can_block(blocker, attacker) is True


class TestTheDawningArchaicAttackTrigger:
    """Attack trigger should free-cast a spell from your graveyard and exile it after use."""

    def test_trigger_does_not_fire_when_another_creature_attacks(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        other_attacker = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        spell = TestSorceryFromGraveyard(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic, other_attacker], graveyard=[spell])

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=other_attacker, attacker=other_attacker),
        )

        assert game.stack.is_empty()
        assert p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_attack_trigger_casts_target_sorcery_for_free_and_exiles_it_after_resolution(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = TestSorceryFromGraveyard(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], mana={})
        p1._script.extend([spell, True])

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert p1.zones[Zone.STACK].contains(spell)
        assert not p1.zones[Zone.GRAVEYARD].contains(spell)

        cast_obj = game.stack.pop()
        cast_obj.on_resolve(game)

        assert spell.resolved is True
        assert p1.life == 23
        assert p1.zones[Zone.EXILE].contains(spell)
        assert not p1.zones[Zone.GRAVEYARD].contains(spell)

    def test_attack_trigger_may_be_declined(self) -> None:
        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        spell = TestSorceryFromGraveyard(owner=p1, controller=p1)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[spell], mana={})
        p1._script.extend([spell, False])

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.GRAVEYARD].contains(spell)
        assert not p1.zones[Zone.EXILE].contains(spell)

    def test_trigger_does_nothing_without_an_instant_or_sorcery_in_your_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        archaic = TheDawningArchaic(owner=p1, controller=p1)
        your_creature = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        opponent_spell = TestSorceryFromGraveyard(owner=p2, controller=p2)

        set_board_state(game, 0, battlefield=[archaic], graveyard=[your_creature])
        set_board_state(game, 1, graveyard=[opponent_spell])

        archaic.register_triggers(game)
        game.trigger_manager.fire_event(
            game,
            AttacksTriggeredEvent(creature=archaic, attacker=archaic),
        )

        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert game.stack.is_empty()
        assert p1.zones[Zone.GRAVEYARD].contains(your_creature)
        assert p2.zones[Zone.GRAVEYARD].contains(opponent_spell)
