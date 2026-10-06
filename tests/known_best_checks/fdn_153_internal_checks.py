"""Known-Best checks moved out of fdn_153's FDN Audited Tests: no FDN card copies a creature spell,
and recasting a creature card from the graveyard takes Zul Ashur, whose {T} cost Known-Best does not
pay (#169), so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_153.card_impl import EssenceScatter
from engine.card import Creature
from engine.casting import cast_spell_free
from engine.decisions import Decision, GameRef
from engine.stack import (
    copy_spell,
    move_spell_off_stack,
    resolve_top_of_stack,
)
from engine.types import Zone
from test_utils import Intent
from test_utils import scenario_game as create_game


class TestEssenceScatterCounters:
    def _game(self):
        game = create_game()
        p1, p2 = game.players
        return game, p1, p2

    def _creature(self, owner, name="Bear"):
        card = Creature(name=name, base_power=2, base_toughness=2, owner=owner)
        card.controller = owner
        return card

    def _cast_scatter_at(self, game, p1, occurrence):
        """Cast Essence Scatter through the real pipeline, selecting
        *occurrence* by its engine-minted stack instance id."""
        scatter = EssenceScatter(owner=p1, controller=p1)
        game.get_hand(p1).add(scatter)
        occ_iid = game.refs.instance_id(occurrence, Zone.STACK.value)
        p1.start_intent(
            "scatter-cast",
            Intent(
                pattern=GameRef(card=frozenset({("printed", EssenceScatter)})),
                preferences=(Decision.obj(instance=occ_iid),),
            ),
        )
        try:
            scatter_so = cast_spell_free(game, p1, scatter, Zone.HAND)
        finally:
            p1.end_intent("scatter-cast")
        assert scatter_so.targets[0] is occurrence
        return scatter, scatter_so





    def test_counter_fizzles_when_occurrence_departed_and_recast(self) -> None:
        """The targeted occurrence left the stack: Essence Scatter fizzles at
        resolution and never touches the re-cast occurrence of the same card."""
        game, p1, p2 = self._game()
        creature = self._creature(p2)
        game.get_hand(p2).add(creature)
        so = cast_spell_free(game, p2, creature, Zone.HAND)

        scatter, _ = self._cast_scatter_at(game, p1, so)

        assert move_spell_off_stack(game, so) is True  # departs (other counter)
        assert game.get_graveyard(p2).contains(creature)
        recast_so = cast_spell_free(game, p2, creature, Zone.GRAVEYARD)
        assert recast_so is not so

        resolve_top_of_stack(game)  # the recast resolves — creature enters
        assert game.get_battlefield(p2).contains(creature)

        resolve_top_of_stack(game)  # Scatter resolves — and fizzles
        assert game.get_battlefield(p2).contains(creature)  # untouched
        assert not game.get_graveyard(p2).contains(creature)
        assert game.get_graveyard(p1).contains(scatter)
        assert game.stack.is_empty()

    def test_copy_countered_distinctly_from_original(self) -> None:
        """A creature-spell COPY is its own occurrence: countering it leaves
        the original cast untouched and moves no card."""
        game, p1, p2 = self._game()
        creature = self._creature(p2)
        game.get_hand(p2).add(creature)
        so = cast_spell_free(game, p2, creature, Zone.HAND)
        copy_so = copy_spell(game, so, p2)
        game.stack.push(copy_so)

        _, scatter_so = self._cast_scatter_at(game, p1, copy_so)
        assert scatter_so.targets[0] is copy_so
        resolve_top_of_stack(game)

        assert not game.stack.contains(copy_so)
        assert game.stack.contains(so)  # original untouched
        assert p2.zones[Zone.STACK].contains(creature)
        assert not game.get_graveyard(p2).contains(creature)
