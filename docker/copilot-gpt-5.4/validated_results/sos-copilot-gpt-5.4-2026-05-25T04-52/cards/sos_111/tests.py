"""Tests for SOS 111 — Choreographed Sparks."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_111.card_impl import ChoreographedSparks
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant, Sorcery
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
from benchmarks.sos.workspace.engine.stack import StackObject, copy_spell
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game


class PracticePing(Instant):
    """Simple targeted instant used to exercise spell-copy behavior."""

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("name", "Test Ping")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(**kwargs)

    def get_targets(self, game: object) -> list[TargetRequirement]:  # noqa: ARG002
        return [
            TargetRequirement(
                filter_fn=lambda obj: isinstance(obj, Creature),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: object) -> None:
        target = getattr(self, "chosen_targets", [None])[0]
        if isinstance(target, Creature):
            target.damage_marked += 2


def _make_creature_spell(*, owner: object, controller: object) -> Creature:
    return Creature(
        name="Stagehand",
        owner=owner,
        controller=controller,
        mana_cost=ManaCost.parse("{1}{R}"),
        base_power=2,
        base_toughness=2,
    )


def _push_spell(
    game: object,
    player: object,
    spell: object,
    *,
    targets: list[object] | None = None,
    on_resolve: object | None = None,
) -> StackObject:
    player.zones[Zone.STACK].add(spell)
    stack_obj = StackObject(
        source=spell,
        controller=player,
        targets=list(targets or []),
        is_spell=True,
        on_resolve=(lambda g: None) if on_resolve is None else on_resolve,
    )
    game.stack.push(stack_obj)
    return stack_obj


class TestChoreographedSparksProperties:
    """Static card data should match the SOS 111 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ChoreographedSparks(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = ChoreographedSparks(owner=None)
        assert card.name == "Choreographed Sparks"
        assert card.mana_cost == ManaCost.parse("{R}{R}")


class TestChoreographedSparksTargeting:
    """The spell should target stack-object spells you control."""

    def test_returns_two_stack_target_requirements(self) -> None:
        game = create_game()
        reqs = ChoreographedSparks(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 2
        assert isinstance(reqs[0], TargetRequirement)
        assert isinstance(reqs[1], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert reqs[1].zone == Zone.STACK

    def test_first_target_accepts_only_your_instant_or_sorcery_spells_on_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = ChoreographedSparks(owner=p1, controller=p1).get_targets(game)[0]

        instant_spell = StackObject(source=Instant(owner=p1, controller=p1), controller=p1, is_spell=True)
        sorcery_spell = StackObject(source=Sorcery(owner=p1, controller=p1), controller=p1, is_spell=True)
        creature_spell = StackObject(
            source=_make_creature_spell(owner=p1, controller=p1),
            controller=p1,
            is_spell=True,
        )
        opposing_spell = StackObject(source=Instant(owner=p2, controller=p2), controller=p2, is_spell=True)
        ability_obj = StackObject(source=object(), controller=p1, is_spell=False)

        assert req.filter_fn(instant_spell) is True
        assert req.filter_fn(sorcery_spell) is True
        assert req.filter_fn(creature_spell) is False
        assert req.filter_fn(opposing_spell) is False
        assert req.filter_fn(ability_obj) is False

    def test_second_target_accepts_only_your_creature_spells_on_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        req = ChoreographedSparks(owner=p1, controller=p1).get_targets(game)[1]

        creature_spell = StackObject(
            source=_make_creature_spell(owner=p1, controller=p1),
            controller=p1,
            is_spell=True,
        )
        instant_spell = StackObject(source=Instant(owner=p1, controller=p1), controller=p1, is_spell=True)
        opposing_creature_spell = StackObject(
            source=_make_creature_spell(owner=p2, controller=p2),
            controller=p2,
            is_spell=True,
        )
        ability_obj = StackObject(source=object(), controller=p1, is_spell=False)

        assert req.filter_fn(creature_spell) is True
        assert req.filter_fn(instant_spell) is False
        assert req.filter_fn(opposing_creature_spell) is False
        assert req.filter_fn(ability_obj) is False


class TestChoreographedSparksResolution:
    """Choreographed Sparks should copy the chosen spell targets."""

    def test_copying_targeted_instant_or_sorcery_spell_can_choose_new_target(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first_target = Creature(
            name="First Target",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        second_target = Creature(
            name="Second Target",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        game.get_battlefield(p2).add(first_target)
        game.get_battlefield(p2).add(second_target)

        original_spell = PracticePing(owner=p1, controller=p1)

        def _resolve_original(g: object) -> None:
            original_spell.chosen_targets = list(original_stack.targets)
            original_spell.on_resolve(g)

        original_stack = _push_spell(
            game,
            p1,
            original_spell,
            targets=[first_target],
            on_resolve=_resolve_original,
        )
        p1._script.append(second_target)

        card = ChoreographedSparks(owner=p1, controller=p1)
        card.chosen_targets = [original_stack]

        card.on_resolve(game)

        assert len(game.stack) == 2
        assert game.stack.peek().source is not original_spell
        assert game.stack.peek().source.name == original_spell.name

        resolve_top(game)
        assert first_target.damage_marked == 0
        assert second_target.damage_marked == 2

        resolve_top(game)
        assert first_target.damage_marked == 2
        assert second_target.damage_marked == 2

    def test_copying_creature_spell_creates_hasty_token_that_sacrifices_at_end_step(self) -> None:
        game = create_game()
        p1 = game.players[0]
        original_spell = _make_creature_spell(owner=p1, controller=p1)
        original_stack = _push_spell(game, p1, original_spell)

        card = ChoreographedSparks(owner=p1, controller=p1)
        card.chosen_targets = [original_stack]

        card.on_resolve(game)

        assert len(game.stack) == 2
        resolve_top(game)

        permanents = game.get_battlefield(p1).get_all()
        tokens = [permanent for permanent in permanents if getattr(permanent, "is_token", False)]
        assert len(tokens) == 1
        token = tokens[0]
        assert token.name == "Stagehand"
        assert token.power == 2
        assert token.toughness == 2
        assert Keyword.HASTE in token.keywords

        game.stack.pop()
        game.trigger_manager.fire_event(game, EndStepTriggeredEvent(player=p1))
        while not game.stack.is_empty():
            resolve_top(game)

        assert not game.get_battlefield(p1).contains(token)

    def test_choosing_both_copies_both_targeted_spells(self) -> None:
        game = create_game()
        p1 = game.players[0]
        instant_stack = _push_spell(game, p1, PracticePing(owner=p1, controller=p1))
        creature_stack = _push_spell(game, p1, _make_creature_spell(owner=p1, controller=p1))

        card = ChoreographedSparks(owner=p1, controller=p1)
        card.chosen_targets = [instant_stack, creature_stack]

        card.on_resolve(game)

        stack_names = [obj.source.name for obj in game.stack.objects()]
        assert stack_names.count("Test Ping") == 2
        assert stack_names.count("Stagehand") == 2


class TestChoreographedSparksCopyRestriction:
    """Choreographed Sparks itself should reject spell-copy effects."""

    def test_spell_on_stack_cannot_be_copied(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = ChoreographedSparks(owner=p1, controller=p1)
        original = StackObject(source=spell, controller=p1, is_spell=True)

        with pytest.raises(Exception, match="copied"):
            copy_spell(game, original, p1)
