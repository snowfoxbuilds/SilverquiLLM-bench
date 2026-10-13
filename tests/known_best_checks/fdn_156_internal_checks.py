"""Known-Best checks of Imprisoned in the Moon's characteristics, which no FDN
card observes through play: an Elf it imprisons has no subtypes, and what it
changed comes back however it stops applying (ADR-018). They also run against
the smoke and fra-hard-v2 Test Oracle Workspaces, which carry the same card."""

from __future__ import annotations

from cards.fdn.fdn_156.card_impl import ImprisonedInTheMoon, ImprisonedInTheMoonAbility2
from cards.fdn.fdn_227.card_impl import LlanowarElves, LlanowarElvesAbility1
from engine.card import Creature
from engine.game import create_token, destroy, exile, mint_token_copy
from engine.priority import activatable_abilities
from engine.types import CardType, Color
from test_utils import behavioral_game, enter_permanent


def _imprison(game, player, permanent):
    """Imprisoned in the Moon resolves onto ``permanent``."""
    moon = enter_permanent(game, player, ImprisonedInTheMoon())
    moon.chosen_targets = [permanent]
    moon.on_resolve(game)
    game.effect_manager.apply_all(game)
    return moon


def _release(game, moon):
    destroy(game, moon)
    game.effect_manager.apply_all(game)


def _printed(game, permanent):
    return [ability.printed for ability in activatable_abilities(permanent, game)]


def _elves():
    game = behavioral_game()
    player = game.players[0]
    return game, player, enter_permanent(game, player, LlanowarElves())


def _vampire(game, player):
    """A black Vampire token: its colour is set on the object, not absent."""
    token = Creature(name="Vampire", subtypes={"Vampire"}, base_power=1, base_toughness=1)
    token.colors = {Color.BLACK}
    return enter_permanent(game, player, token)


class TestWhileImprisoned:
    def test_an_imprisoned_elf_is_a_colorless_land_with_no_subtypes(self) -> None:
        game, player, elves = _elves()
        _imprison(game, player, elves)
        assert elves.card_types == {CardType.LAND}
        assert elves.subtypes == set()
        assert elves.colors == set()
        assert _printed(game, elves) == [ImprisonedInTheMoonAbility2]


class TestRelease:
    def test_destroying_the_aura_gives_back_types_and_no_color_override(self) -> None:
        game, player, elves = _elves()
        _release(game, _imprison(game, player, elves))
        assert CardType.CREATURE in elves.card_types
        assert elves.subtypes == {"Elf", "Druid"}
        assert "colors" not in elves.__dict__
        assert _printed(game, elves) == [LlanowarElvesAbility1]

    def test_a_token_gets_its_own_color_back(self) -> None:
        game = behavioral_game()
        player = game.players[0]
        vampire = _vampire(game, player)
        moon = _imprison(game, player, vampire)
        assert vampire.colors == set()
        _release(game, moon)
        assert vampire.colors == {Color.BLACK}
        assert vampire.subtypes == {"Vampire"}

    def test_leaving_the_battlefield_while_imprisoned_gives_everything_back(self) -> None:
        game, player, elves = _elves()
        _imprison(game, player, elves)
        exile(game, elves)
        game.effect_manager.apply_all(game)
        assert CardType.CREATURE in elves.card_types
        assert elves.subtypes == {"Elf", "Druid"}
        assert "colors" not in elves.__dict__


class TestTwoAuras:
    def test_one_aura_leaving_keeps_the_other_applying(self) -> None:
        game, player, elves = _elves()
        first = _imprison(game, player, elves)
        second = _imprison(game, player, elves)
        _release(game, first)
        assert elves.card_types == {CardType.LAND}
        assert elves.subtypes == set()
        assert elves.colors == set()
        assert _printed(game, elves) == [ImprisonedInTheMoonAbility2]
        _release(game, second)
        assert elves.subtypes == {"Elf", "Druid"}
        assert "colors" not in elves.__dict__
        assert _printed(game, elves) == [LlanowarElvesAbility1]


class TestTokenCopy:
    def test_a_copy_of_a_once_imprisoned_elf_answers_for_itself(self) -> None:
        """A token copy of Llanowar Elves made after its Aura left keeps its {G}
        when another Aura imprisons the original."""
        game, player, elves = _elves()
        _release(game, _imprison(game, player, elves))
        [token] = create_token(game, player, mint_token_copy(elves))
        _imprison(game, player, elves)
        assert _printed(game, elves) == [ImprisonedInTheMoonAbility2]
        assert _printed(game, token) == [LlanowarElvesAbility1]
        assert token.subtypes == {"Elf", "Druid"}
