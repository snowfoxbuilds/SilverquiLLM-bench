"""Known-Best checks that a spell copied after it left the stack is copied as it
last existed there (rule 707.10): Thousand-Year Storm's trigger copies a
countered spell with that spell's own X, mode and targets, even after the card
has been cast again with other choices.

They drive the engine directly with synthetic spells, which no Audited Test
may use (ADR-018).
"""

from __future__ import annotations

from typing import Any

from cards.fdn.fdn_188.card_impl import Abrade, AbradeAbility3
from cards.fdn.fdn_215.card_impl import Bushwhack, BushwhackAbility3
from cards.fdn.fdn_248.card_impl import ThousandYearStorm
from engine.card import Creature, Equipment, Instant, printed_class
from engine.casting import cast_spell as engine_cast_spell
from engine.decisions import Decision, GameRef
from engine.stack import copy_spell, copyable_occurrence, move_spell_off_stack, resolve_top_of_stack
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from engine.zones import move_to_zone
from test_utils import Intent, create_game, set_board_state


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class _Signal(Instant):
    """A {0} instant with no targets, cast first so the next spell is copied."""

    def __init__(self, name: str = "Signal", **kwargs: Any) -> None:
        kwargs.setdefault("name", name)
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return []

    def on_resolve(self, game: Any) -> None:
        return None


class _XBurn(Instant):
    """{X}: deals X damage to target creature."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "X Burn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return [TargetRequirement(filter_fn=_is_creature, description="target creature", zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or []
        if chosen and chosen[0] is not None and _is_creature(chosen[0]):
            deal_damage(game, self, chosen[0], self.x_value)


class _Bolt(Instant):
    """{0}: deals 5 damage to target creature."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bolt")
        kwargs.setdefault("mana_cost", ManaCost.parse("{0}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return [TargetRequirement(filter_fn=_is_creature, description="target creature", zone=Zone.BATTLEFIELD)]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or []
        if chosen and chosen[0] is not None and _is_creature(chosen[0]):
            deal_damage(game, self, chosen[0], 5)


class _XUpTo(Instant):
    """{X}: deals X damage to target creature with power X or less. The target
    filter closes over the card, as a filter written in ``get_targets`` does."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "X Up To")
        kwargs.setdefault("mana_cost", ManaCost.parse("{X}"))
        super().__init__(**kwargs)

    def get_targets(self, game: Any) -> list:
        return [TargetRequirement(
            filter_fn=lambda obj: _is_creature(obj) and obj.base_power <= self.x_value,
            description="target creature with power X or less",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or []
        if chosen and chosen[0] is not None and _is_creature(chosen[0]):
            deal_damage(game, self, chosen[0], self.x_value)


class _XUpToByDefault(_XUpTo):
    """The same spell with the card captured as a default argument."""

    def get_targets(self, game: Any) -> list:
        def small_enough(obj: Any, card: Any = self) -> bool:
            return _is_creature(obj) and obj.base_power <= card.x_value

        return [TargetRequirement(
            filter_fn=small_enough, description="target creature with power X or less", zone=Zone.BATTLEFIELD,
        )]


def _creature(p, name):
    return Creature(name=name, base_power=1, base_toughness=50, owner=p, controller=p)


def _big_creature(p, name):
    return Creature(name=name, base_power=4, base_toughness=50, owner=p, controller=p)


def _equipment(p, name):
    return Equipment(name=name, owner=p, controller=p, equip_cost=ManaCost.parse("{1}"))


def _pref(game, obj):
    return Decision.obj(instance=game.refs.instance_id(obj, Zone.BATTLEFIELD.value))


def _setup(hand, opponent_battlefield, *, mana=None):
    game = create_game()
    p1, p2 = game.players
    storm = ThousandYearStorm(owner=p1, controller=p1)
    set_board_state(game, 0, hand=hand, battlefield=[storm], mana=mana or {})
    set_board_state(game, 1, battlefield=list(opponent_battlefield))
    game.active_player_index = 0
    storm.register_triggers(game)
    return game, p1


def _cast(game, p1, spell, prefs=()):
    """Cast *spell*, answering its cast-time questions with *prefs*; then settle
    so the Storm trigger it fired is on the stack."""
    p1.start_intent("cast", Intent(
        pattern=GameRef(card=frozenset({("printed", printed_class(spell))})),
        preferences=tuple(prefs),
    ))
    try:
        engine_cast_spell(game, p1, spell)
    finally:
        p1.end_intent("cast")
    resolve_state_based_actions(game)


def _occurrence(game, spell):
    return next(so for so in game.stack._items if so.source is spell and so.is_spell)


def _counter(game, spell, to_zone=Zone.GRAVEYARD):
    """Counter *spell* through the shared departure primitive, as a
    counterspell does (or a counter-and-return when *to_zone* is the hand)."""
    move_spell_off_stack(game, _occurrence(game, spell), to_zone)


def _storm_answers(p1, *, retarget: bool, spell_cls=None, target_prefs=()):
    """Answer the Storm trigger's retarget question, and (for *spell_cls*) the
    copy's target questions, which are raised as the copied spell."""
    p1.start_intent("storm", Intent(
        pattern=GameRef(card=frozenset({("printed", ThousandYearStorm)})),
        preferences=(Decision.yes(),) if retarget else (Decision.no(),),
    ))
    if spell_cls is not None:
        p1.start_intent("copytarget", Intent(
            pattern=GameRef(card=frozenset({("printed", spell_cls)})),
            preferences=tuple(target_prefs),
        ))
    return lambda: _end_storm_answers(p1, spell_cls is not None)


def _end_storm_answers(p1, copy_targets: bool):
    p1.end_intent("storm")
    if copy_targets:
        p1.end_intent("copytarget")


def _resolve_all_collect_copies(game):
    """Resolve the whole stack; return every spell copy pushed along the way,
    in the order they were made."""
    made = []
    while game.stack._items:
        before = list(game.stack._items)
        resolve_top_of_stack(game)
        resolve_state_based_actions(game)
        made += [so for so in game.stack._items if all(so is not b for b in before) and so.is_spell]
    return made


class TestCountedSpellIsCopiedAsItLastExisted:
    def test_countered_occurrence_keeps_its_x_after_recast(self):
        """X Burn (X=3) is countered back to its owner's hand and cast again
        with X=5 while its first Storm trigger is still waiting. The later
        trigger makes two X=5 copies; the earlier one still makes its copy with
        X=3, the X that occurrence was cast with."""
        signal, burn = _Signal(), _XBurn()
        game, p1 = _setup([signal, burn], [], mana={ManaType.COLORLESS: 8})
        target = _creature(game.players[1], "Target")
        set_board_state(game, 1, battlefield=[target])
        _cast(game, p1, signal)
        _cast(game, p1, burn, [Decision.number(3), _pref(game, target)])
        _counter(game, burn, Zone.HAND)
        _cast(game, p1, burn, [Decision.number(5), _pref(game, target)])

        done = _storm_answers(p1, retarget=False)
        made = _resolve_all_collect_copies(game)
        done()

        assert [so.source.x_value for so in made] == [5, 5, 3]
        assert target.damage_marked == 5 + 5 + 5 + 3

    def test_countered_x_spell_copy_keeps_its_x(self):
        signal, burn = _Signal(), _XBurn()
        game, p1 = _setup([signal, burn], [], mana={ManaType.COLORLESS: 4})
        target = _creature(game.players[1], "Target")
        set_board_state(game, 1, battlefield=[target])
        _cast(game, p1, signal)
        _cast(game, p1, burn, [Decision.number(4), _pref(game, target)])
        _counter(game, burn)

        done = _storm_answers(p1, retarget=False)
        made = _resolve_all_collect_copies(game)
        done()

        assert [so.source.x_value for so in made] == [4]
        assert target.damage_marked == 4
        assert game.get_graveyard(p1).contains(burn)

    def test_countered_modal_spell_copy_keeps_its_mode(self):
        """Abrade cast for its artifact mode and countered: the copy keeps that
        mode, so a new target is chosen among artifacts and the mode is not
        asked again."""
        signal, abrade = _Signal(), Abrade()
        game, p1 = _setup([signal, abrade], [], mana={ManaType.RED: 1, ManaType.COLORLESS: 1})
        p2 = game.players[1]
        first, second, bystander = _equipment(p2, "First"), _equipment(p2, "Second"), _creature(p2, "Bystander")
        set_board_state(game, 1, battlefield=[first, second, bystander])
        _cast(game, p1, signal)
        _cast(game, p1, abrade, [Decision.mode(printed=AbradeAbility3), _pref(game, first)])
        _counter(game, abrade)

        done = _storm_answers(p1, retarget=True, spell_cls=Abrade, target_prefs=(_pref(game, second),))
        made = _resolve_all_collect_copies(game)
        done()

        assert len(made) == 1
        assert game.get_graveyard(p2).contains(second)
        assert not game.get_graveyard(p2).contains(first)
        assert bystander.damage_marked == 0

    def test_countered_spell_copy_keeps_its_target(self):
        signal, bolt = _Signal(), _Bolt()
        game, p1 = _setup([signal, bolt], [])
        p2 = game.players[1]
        aimed, other = _creature(p2, "Aimed"), _creature(p2, "Other")
        set_board_state(game, 1, battlefield=[aimed, other])
        _cast(game, p1, signal)
        _cast(game, p1, bolt, [_pref(game, aimed)])
        _counter(game, bolt)

        done = _storm_answers(p1, retarget=False)
        made = _resolve_all_collect_copies(game)
        done()

        assert [so.targets for so in made] == [[aimed]]
        assert (aimed.damage_marked, other.damage_marked) == (5, 0)

    def test_countered_spell_copy_takes_a_new_target(self):
        signal, bolt = _Signal(), _Bolt()
        game, p1 = _setup([signal, bolt], [])
        p2 = game.players[1]
        aimed, other = _creature(p2, "Aimed"), _creature(p2, "Other")
        set_board_state(game, 1, battlefield=[aimed, other])
        _cast(game, p1, signal)
        _cast(game, p1, bolt, [_pref(game, aimed)])
        _counter(game, bolt)

        done = _storm_answers(p1, retarget=True, spell_cls=_Bolt, target_prefs=(_pref(game, other),))
        made = _resolve_all_collect_copies(game)
        done()

        assert [so.targets for so in made] == [[other]]
        assert (aimed.damage_marked, other.damage_marked) == (0, 5)

    def test_retained_target_that_left_and_returned_is_not_hit(self):
        signal, bolt = _Signal(), _Bolt()
        game, p1 = _setup([signal, bolt], [])
        p2 = game.players[1]
        aimed = _creature(p2, "Aimed")
        set_board_state(game, 1, battlefield=[aimed])
        _cast(game, p1, signal)
        _cast(game, p1, bolt, [_pref(game, aimed)])
        _counter(game, bolt)
        move_to_zone(game, aimed, Zone.BATTLEFIELD, Zone.EXILE)
        move_to_zone(game, aimed, Zone.EXILE, Zone.BATTLEFIELD)

        done = _storm_answers(p1, retarget=False)
        _resolve_all_collect_copies(game)
        done()

        assert aimed.damage_marked == 0


class TestLiveSpellIsCopiedFromTheCard:
    def test_live_original_is_copied_from_the_card_and_snapshotted_on_departure(self):
        from engine.stack import copyable_occurrence

        signal, burn = _Signal(), _XBurn()
        game, p1 = _setup([signal, burn], [], mana={ManaType.COLORLESS: 3})
        target = _creature(game.players[1], "Target")
        set_board_state(game, 1, battlefield=[target])
        _cast(game, p1, signal)
        _cast(game, p1, burn, [Decision.number(3), _pref(game, target)])
        occurrence = _occurrence(game, burn)
        assert occurrence.last_known_source is None
        assert copyable_occurrence(occurrence) is occurrence

        done = _storm_answers(p1, retarget=False)
        made = _resolve_all_collect_copies(game)
        done()

        assert [so.source.x_value for so in made] == [3]
        assert target.damage_marked == 3 + 3
        assert occurrence.last_known_source is not None
        assert occurrence.last_known_source is not burn

    def test_countered_copy_departs_with_its_own_snapshot(self):
        """A spell copy leaves the stack through the same primitive: no card
        moves, and the copy keeps a snapshot of itself."""
        signal = _Signal()
        game, p1 = _setup([signal], [])
        _cast(game, p1, signal)
        copy_obj = copy_spell(game, _occurrence(game, signal), p1)
        game.stack.push(copy_obj)

        assert move_spell_off_stack(game, copy_obj)
        assert copy_obj.last_known_source is not None
        assert copy_obj.last_known_source is not copy_obj.source
        assert any(so.source is signal for so in game.stack._items)


class TestRetargetingJudgesTheOccurrenceNotTheCard:
    """Choosing new targets for a copy of a countered spell judges legality by
    that occurrence's choices: its target filters read the snapshot, not the
    card, which a later cast may have changed."""

    def _recast_x_up_to(self, spell_cls):
        signal, spell = _Signal(), spell_cls()
        game, p1 = _setup([signal, spell], [], mana={ManaType.COLORLESS: 8})
        p2 = game.players[1]
        big, small = _big_creature(p2, "Big"), _creature(p2, "Small")
        set_board_state(game, 1, battlefield=[big, small])
        _cast(game, p1, signal)
        _cast(game, p1, spell, [Decision.number(3), _pref(game, small)])
        _counter(game, spell, Zone.HAND)
        _cast(game, p1, spell, [Decision.number(5), _pref(game, small)])

        # Each copy retargets to Big when Big is legal for it, otherwise Small.
        done = _storm_answers(
            p1, retarget=True, spell_cls=spell_cls, target_prefs=(_pref(game, big), _pref(game, small)),
        )
        made = _resolve_all_collect_copies(game)
        done()
        return made, big, small

    def test_a_filter_closing_over_the_card_reads_the_occurrences_x(self):
        """X=3 was countered and the card recast with X=5. The two X=5 copies
        may take Big (power 4); the X=3 copy may not, so it takes Small."""
        made, big, small = self._recast_x_up_to(_XUpTo)

        assert [so.source.x_value for so in made] == [5, 5, 3]
        assert [so.targets for so in made] == [[big], [big], [small]]
        assert (big.damage_marked, small.damage_marked) == (10, 8)

    def test_a_filter_with_the_card_as_a_default_argument_reads_the_occurrences_x(self):
        made, big, small = self._recast_x_up_to(_XUpToByDefault)

        assert [so.targets for so in made] == [[big], [big], [small]]
        assert (big.damage_marked, small.damage_marked) == (10, 8)

    def test_a_bound_method_filter_reads_the_occurrences_controller(self):
        """Player 0 casts player 1's Bushwhack to fight; it is countered, and
        the card goes back to its owner. The copy's "you control" is still
        player 0's, as it was for that occurrence."""
        signal = _Signal()
        game, p1 = _setup([signal], [], mana={ManaType.GREEN: 1})
        p2 = game.players[1]
        bushwhack = Bushwhack(owner=p2, controller=p1)
        p1.zones[Zone.HAND].add(bushwhack)
        mine, other_mine = _creature(p1, "Mine"), _creature(p1, "Other Mine")
        theirs, other_theirs = _creature(p2, "Theirs"), _creature(p2, "Other Theirs")
        p1.zones[Zone.BATTLEFIELD].add(mine)
        p1.zones[Zone.BATTLEFIELD].add(other_mine)
        p2.zones[Zone.BATTLEFIELD].add(theirs)
        p2.zones[Zone.BATTLEFIELD].add(other_theirs)
        _cast(game, p1, signal)
        _resolve_all_collect_copies(game)  # a sorcery needs an empty stack
        game.phase = Phase.PRECOMBAT_MAIN  # ... and a main phase
        _cast(game, p1, bushwhack, [
            Decision.mode(printed=BushwhackAbility3), _pref(game, mine), _pref(game, theirs),
        ])
        occurrence = _occurrence(game, bushwhack)
        _counter(game, bushwhack)
        bushwhack.controller = p2  # the card is its owner's again

        departed = copyable_occurrence(occurrence)
        yours, not_yours = departed.target_requirements
        assert yours.filter_fn(other_mine) and not yours.filter_fn(other_theirs)
        assert not_yours.filter_fn(other_theirs) and not not_yours.filter_fn(other_mine)

        done = _storm_answers(
            p1, retarget=True, spell_cls=Bushwhack, target_prefs=(_pref(game, other_mine), _pref(game, other_theirs)),
        )
        made = _resolve_all_collect_copies(game)
        done()

        assert [so.targets for so in made] == [[other_mine, other_theirs]]
        assert (other_mine.damage_marked, other_theirs.damage_marked) == (1, 1)
        assert (mine.damage_marked, theirs.damage_marked) == (0, 0)

    def test_requirements_that_never_read_the_card_are_kept_as_they_are(self):
        signal, bolt = _Signal(), _Bolt()
        game, p1 = _setup([signal, bolt], [])
        aimed = _creature(game.players[1], "Aimed")
        set_board_state(game, 1, battlefield=[aimed])
        _cast(game, p1, signal)
        _cast(game, p1, bolt, [_pref(game, aimed)])
        occurrence = _occurrence(game, bolt)
        _counter(game, bolt)

        departed = copyable_occurrence(occurrence)
        assert departed.source is occurrence.last_known_source
        assert departed.target_requirements[0] is occurrence.target_requirements[0]
        assert occurrence.target_requirements[0].filter_fn is _is_creature
