"""Known-Best tests place, choose, route and assert by predefined classes
(DECISION-MODEL.md › Printed identity › No raw strings), and a planeswalker with
no loyalty leaves the battlefield (CR 704.5i).

Run inside ``known_best/workspace`` by ``tests/test_known_best_no_raw_strings.py``:
the module imports the workspace's ``engine`` and ``test_utils``, which the repo
suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

import pytest
from engine.card import Creature, Instant, Planeswalker, printed_class
from engine.card_queries import choose_mode
from engine.decisions import Decision, GameRef
from test_utils import Intent
from engine.state_based_actions import check_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Phase, Step, TargetRequirement, Zone
from test_utils import (
    TestSetupError as SetupError,
)
from test_utils import (
    act,
    cast_spell,
    create_game,
    declare_attackers,
    declare_blockers,
    script,
    set_board_state,
    source_pattern,
)


class Bear(Creature):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("name", "Bear")
        super().__init__(mana_cost=ManaCost(), base_power=2, base_toughness=2, **kwargs)


class Shock(Instant):
    """Deals 2 damage to target creature."""

    def __init__(self, **kwargs) -> None:
        super().__init__(name="Shock", mana_cost=ManaCost(pips={ManaType.RED: 1}), **kwargs)

    def get_targets(self, game):
        return [TargetRequirement(
            filter_fn=lambda o: CardType.CREATURE in getattr(o, "card_types", set()),
            description="target creature",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game):
        for target in getattr(self, "chosen_targets", None) or []:
            target.damage_marked += 2


class Walker(Planeswalker):
    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("starting_loyalty", 3)
        super().__init__(name="Walker", mana_cost=ManaCost(), **kwargs)


class Mode1:
    """A printed mode."""


class Mode2:
    """A printed mode."""


class TestPrintedRouting:
    def test_query_sources_carry_the_printed_class(self):
        game = create_game()
        p0 = game.players[0]
        shock = Shock()
        p0.start_intent("modes", Intent(
            pattern=source_pattern(Shock),
            preferences=(Decision.mode(printed=Mode2),),
        ))
        chosen = choose_mode(game, p0, ["one", "two"], "choose", source_card=shock,
                             printed=[Mode1, Mode2])
        p0.end_intent("modes")
        assert chosen == "two"
        assert ("printed", Shock) in p0.transcript.all()[-1].query.source[0].ref.card

    def test_cast_spell_routes_targets_by_printed_class(self):
        game = create_game()
        near, far = Bear(), Bear()
        set_board_state(game, 1, battlefield=[near, far])
        set_board_state(game, 0, hand=[Shock()], mana={ManaType.RED: 1})
        cast_spell(game, 0, Shock, targets=[far])
        assert game.get_battlefield(game.players[1]).contains(near)
        assert game.get_graveyard(game.players[1]).contains(far)

    def test_a_synthetic_object_routes_by_itself(self):
        generic = Instant(name="Untitled", mana_cost=ManaCost())
        assert printed_class(generic) is None
        assert dict(source_pattern(generic).card) == {"name": generic.name}
        assert source_pattern(Shock()) == GameRef(card=frozenset({("printed", Shock)}))


class TestHelpersRefuseNames:
    def test_cast_spell(self):
        game = create_game()
        set_board_state(game, 0, hand=[Shock()], mana={ManaType.RED: 1})
        with pytest.raises(SetupError, match="name string"):
            cast_spell(game, 0, "Shock")

    def test_declarations(self):
        game = create_game()
        attacker, blocker = Bear(), Bear()
        attacker.summoning_sick = False
        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[blocker])
        game.active_player_index = 0
        with pytest.raises(SetupError, match="name string"):
            declare_attackers(game, ["Bear"])
        declare_attackers(game, [Bear])
        assert attacker.is_attacking
        with pytest.raises(SetupError, match="name string"):
            declare_blockers(game, {attacker: ["Bear"]})
        declare_blockers(game, {Bear: [Bear]})
        assert blocker.is_blocking

    def test_source_pattern(self):
        with pytest.raises(SetupError, match="name string"):
            source_pattern("Shock")

    def test_a_class_with_no_object_is_not_found(self):
        game = create_game()
        set_board_state(game, 0, hand=[Bear()])
        with pytest.raises(SetupError, match="Shock not found in player 0's hand"):
            cast_spell(game, 0, Shock)


class TestPlaneswalkerZeroLoyalty:
    def test_zero_loyalty_goes_to_graveyard(self):
        game = create_game()
        walker = Walker()
        set_board_state(game, 1, battlefield=[walker])
        walker.loyalty = 0
        assert check_state_based_actions(game) is True
        assert game.get_graveyard(game.players[1]).contains(walker)

    def test_positive_loyalty_stays(self):
        game = create_game()
        walker = Walker()
        set_board_state(game, 1, battlefield=[walker])
        assert check_state_based_actions(game) is False
        assert game.get_battlefield(game.players[1]).contains(walker)

    def test_lethal_combat_damage_removes_the_walker(self):
        from engine.combat import combat_damage_step, declare_attackers_step

        game = create_game()
        attacker = Bear()
        attacker.summoning_sick = False
        walker = Walker(starting_loyalty=2)
        set_board_state(game, 0, battlefield=[attacker])
        set_board_state(game, 1, battlefield=[walker])
        game.active_player_index = 0
        game.phase, game.step = Phase.COMBAT, Step.DECLARE_ATTACKERS
        script(game, 0, act(Bear, scoped={Bear: Walker}))
        declare_attackers_step(game)
        combat_damage_step(game)
        check_state_based_actions(game)
        assert game.get_graveyard(game.players[1]).contains(walker)
