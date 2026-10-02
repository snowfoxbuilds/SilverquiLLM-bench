"""The FDN gain-life tapland cycle gains life via a real ETB trigger.

Phase G (cadence alignment): "When this land enters, you gain 1 life" is a
triggered ability, not an as-enters effect. It is registered as a real
EntersBattlefield trigger so it goes on the stack when the land enters and
resolves at its own cadence — which is what makes the replay executor's life
match GRE (GRE reports the clause as an ability that activates then resolves a
step or two later, not an instantaneous land-play side effect). "Enters tapped"
stays an as-enters effect applied at drive time.
"""

from __future__ import annotations

from cards.fdn.gainlife_taplands import make_gainlife_tapland
from engine.game_state import GameState
from engine.intent_player import DeterministicPlayer
from engine.types import ManaType, Phase


def _make_game() -> GameState:
    game = GameState([DeterministicPlayer("Alice"), DeterministicPlayer("Bob")])
    game.phase = Phase.PRECOMBAT_MAIN
    return game


def _tapland():
    cls = make_gainlife_tapland("Test Crag", (ManaType.RED, ManaType.WHITE), 999)
    return cls()


class TestGainlifeTaplandTrigger:
    def test_life_not_gained_at_drive_time(self) -> None:
        """play_land enters the land tapped but does NOT gain life immediately —
        the life is a triggered ability now on the stack, not an as-enters
        effect."""
        from engine.casting import play_land

        game = _make_game()
        player = game.players[0]
        land = _tapland()
        game.get_hand(player).add(land)

        play_land(game, player, land)

        assert game.get_battlefield(player).contains(land)
        assert land.is_tapped is True
        assert player.life == 20  # NOT yet gained
        # The gain-1-life trigger is on the stack, sourced by the land.
        assert not game.stack.is_empty()
        assert any(obj.source is land for obj in game.stack.objects())

    def test_life_gained_when_trigger_resolves(self) -> None:
        """Resolving the ETB trigger gains the controller exactly 1 life."""
        from engine.casting import play_land
        from engine.stack import resolve_top_of_stack

        game = _make_game()
        player = game.players[0]
        land = _tapland()
        game.get_hand(player).add(land)

        play_land(game, player, land)
        resolve_top_of_stack(game)

        assert player.life == 21
        assert game.stack.is_empty()

    def test_trigger_gains_life_once_not_per_resolve_call(self) -> None:
        """The trigger fires once per entry (one +1), not once per settle pass."""
        from engine.casting import play_land
        from engine.stack import resolve_top_of_stack

        game = _make_game()
        player = game.players[0]
        land = _tapland()
        game.get_hand(player).add(land)

        play_land(game, player, land)
        resolve_top_of_stack(game)
        # Stack is empty; a further settle must not re-gain.
        resolve_top_of_stack(game)

        assert player.life == 21
