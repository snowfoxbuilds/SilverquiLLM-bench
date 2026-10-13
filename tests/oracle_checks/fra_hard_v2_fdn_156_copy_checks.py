"""fra-hard-v2 Test Oracle checks of Imprisoned in the Moon against the copy
lifecycle only that oracle has: Hall of Echoes becoming a copy until end of
turn, a copy starting on an imprisoned permanent, and the copiable values of
one. Imprisoned in the Moon is an FDN card, so these stay out of Hall of
Echoes' graded suite."""

from __future__ import annotations

from cards.fdn.fdn_156.card_impl import ImprisonedInTheMoon, ImprisonedInTheMoonAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves, LlanowarElvesAbility1
from cards.fra.fra_179.card_impl import HallOfEchoes, HallOfEchoesAbility1, HallOfEchoesAbility2
from engine.card import Creature
from engine.copying import become_copy, copiable_values
from engine.game import destroy
from engine.priority import activatable_abilities
from engine.types import CardType, Color
from test_utils import behavioral_game, enter_permanent


def _imprison(game, player, permanent):
    moon = enter_permanent(game, player, ImprisonedInTheMoon())
    moon.chosen_targets = [permanent]
    moon.on_resolve(game)
    game.effect_manager.apply_all(game)
    return moon


def _release(game, moon):
    destroy(game, moon)
    game.effect_manager.apply_all(game)


def _end_of_turn(game):
    """Cleanup: "until end of turn" copy effects end and effects reapply."""
    game.effect_manager.remove_expired(game)
    game.effect_manager.apply_all(game)


def _printed(game, permanent):
    return {ability.printed for ability in activatable_abilities(permanent, game)}


def _vampire(game, player):
    token = Creature(name="Vampire", subtypes={"Vampire"}, base_power=1, base_toughness=1)
    token.colors = {Color.BLACK}
    return enter_permanent(game, player, token)


def _hall_copying(game, player, creature):
    hall = enter_permanent(game, player, HallOfEchoes())
    become_copy(game, hall, creature)
    game.effect_manager.apply_all(game)
    return hall


def _assert_plain_hall(game, hall):
    assert type(hall) is HallOfEchoes
    assert hall.card_types == {CardType.LAND}
    assert hall.subtypes == set()
    assert "colors" not in hall.__dict__
    assert _printed(game, hall) == {HallOfEchoesAbility1, HallOfEchoesAbility2}


class TestHallOfEchoes:
    def test_aura_removed_after_the_copy_ends_leaves_hall_as_itself(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        hall = _hall_copying(game, player, enter_permanent(game, player, LlanowarElves()))
        moon = _imprison(game, player, hall)
        _end_of_turn(game)
        assert type(hall) is HallOfEchoes
        assert hall.subtypes == set()
        assert _printed(game, hall) == {ImprisonedInTheMoonAbility2}
        _release(game, moon)
        _assert_plain_hall(game, hall)

    def test_aura_removed_before_the_copy_ends_leaves_the_copy_then_hall(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        hall = _hall_copying(game, player, enter_permanent(game, player, LlanowarElves()))
        _release(game, _imprison(game, player, hall))
        assert CardType.CREATURE in hall.card_types
        assert hall.subtypes == {"Elf", "Druid"}
        assert _printed(game, hall) == {LlanowarElvesAbility1}
        _end_of_turn(game)
        _assert_plain_hall(game, hall)

    def test_a_copied_tokens_color_and_type_do_not_stay_on_hall(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        hall = _hall_copying(game, player, _vampire(game, player))
        assert hall.colors == {Color.BLACK}
        moon = _imprison(game, player, hall)
        assert hall.colors == set()
        _end_of_turn(game)
        _release(game, moon)
        _assert_plain_hall(game, hall)


class TestCopyStartingWhileImprisoned:
    def test_the_copy_and_then_the_permanent_get_their_own_values_back(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        elves = enter_permanent(game, player, LlanowarElves())
        moon = _imprison(game, player, elves)
        become_copy(game, elves, _vampire(game, player))
        game.effect_manager.apply_all(game)
        assert elves.card_types == {CardType.LAND}
        assert elves.subtypes == set()
        assert elves.colors == set()
        _release(game, moon)
        assert CardType.CREATURE in elves.card_types
        assert elves.subtypes == {"Vampire"}
        assert elves.colors == {Color.BLACK}
        _end_of_turn(game)
        assert type(elves) is LlanowarElves
        assert elves.subtypes == {"Elf", "Druid"}
        assert "colors" not in elves.__dict__
        assert _printed(game, elves) == {LlanowarElvesAbility1}


class TestCopiableValues:
    def test_an_imprisoned_permanents_copiable_values_exclude_the_aura(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        elves = enter_permanent(game, player, LlanowarElves())
        _imprison(game, player, elves)
        values = copiable_values(elves)
        assert values["card_types"] == {CardType.CREATURE}
        assert values["subtypes"] == {"Elf", "Druid"}
        assert "colors" not in values
