"""Phase 2 protocol tests: targeting raises Player Queries offering only legal
options, and the Answer maps back to the chosen game object.

Uses a tiny concrete Player double (the intent-based DeterministicPlayer lands
in Phase 3); these tests exercise the engine's query construction, not the
player's intent layer.
"""

from __future__ import annotations

from engine.card import Creature, Instant
from engine.decisions import DecisionKind, satisfies
from engine.game_state import GameState
from engine.player import Player
from engine.queries import Answer
from engine.types import CardType, Keyword, ManaCost, Zone


class PrefPlayer(Player):
    """Answers by first option satisfying a preference; logs a transcript."""

    def __init__(self, name: str, prefs=()):
        super().__init__(name)
        self.prefs = list(prefs)
        self.transcript: list = []

    def answer(self, query) -> Answer:
        self.transcript.append(query)
        for pref in self.prefs:
            for opt in query.options:
                if satisfies(opt, pref):
                    return Answer(selected=(opt,))
        return Answer(selected=tuple(query.options[: query.min]))


def _creature(name: str, *, keywords: Keyword = Keyword(0)) -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost(generic=1),
        base_power=1,
        base_toughness=1,
        keywords=keywords,
    )


def _targeted_instant(filter_fn) -> Instant:
    from engine.types import TargetRequirement

    spell = Instant(name="Zap", mana_cost=ManaCost(), card_types={CardType.INSTANT})

    def get_targets(game):
        return [
            TargetRequirement(
                filter_fn=filter_fn,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    spell.get_targets = get_targets  # type: ignore[method-assign]
    return spell


def _put(game, player, zone, card):
    card.owner = player
    card.controller = player
    player.zones[zone].add(card)


class TestTargetingQuery:
    def test_only_legal_targets_are_offered(self):
        from engine.casting import cast_spell

        p0, p1 = PrefPlayer("P0"), PrefPlayer("P1")
        game = GameState([p0, p1])

        plain = _creature("Bear")
        hexer = _creature("Hexer", keywords=Keyword.HEXPROOF)
        _put(game, p1, Zone.BATTLEFIELD, plain)
        _put(game, p1, Zone.BATTLEFIELD, hexer)

        spell = _targeted_instant(
            lambda o: CardType.CREATURE in getattr(o, "card_types", set())
            and Keyword.HEXPROOF not in getattr(o, "keywords", Keyword(0))
        )
        _put(game, p0, Zone.HAND, spell)

        cast_spell(game, p0, spell)

        # Exactly one query was raised, of OBJECT kind.
        assert len(p0.transcript) == 1
        query = p0.transcript[0]
        assert all(opt.kind is DecisionKind.OBJECT for opt in query.options)
        # Option-set invariant: the engine never offered the hexproof creature.
        assert not any(("keyword", "hexproof") in opt.attrs for opt in query.options)
        assert any(("name", "Bear") in opt.attrs for opt in query.options)

    def test_chosen_target_maps_back_to_game_object(self):
        from engine.casting import cast_spell

        p0, p1 = PrefPlayer("P0"), PrefPlayer("P1")
        game = GameState([p0, p1])
        bear = _creature("Bear")
        _put(game, p1, Zone.BATTLEFIELD, bear)

        spell = _targeted_instant(
            lambda o: CardType.CREATURE in getattr(o, "card_types", set())
        )
        _put(game, p0, Zone.HAND, spell)

        cast_spell(game, p0, spell)

        chosen = game.stack.peek().targets
        assert chosen == [bear]

    def test_no_legal_target_raises_casting_error(self):
        from engine.casting import CastingError, cast_spell

        p0, p1 = PrefPlayer("P0"), PrefPlayer("P1")
        game = GameState([p0, p1])
        # No creatures anywhere → no legal target for a required spec.
        spell = _targeted_instant(
            lambda o: CardType.CREATURE in getattr(o, "card_types", set())
        )
        _put(game, p0, Zone.HAND, spell)

        try:
            cast_spell(game, p0, spell)
        except CastingError:
            return
        raise AssertionError("expected CastingError for no legal target")
