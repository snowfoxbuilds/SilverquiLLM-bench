"""Known-Best checks moved out of fdn_131's FDN Audited Tests: #169: Known-Best's Ravenous Amulet sacrifices itself on resolution instead of as a cost,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_131.card_impl import RavenousAmulet
from engine.game import add_counter, exile
from engine.types import ManaType
from test_utils import activate_card_ability, behavioral_game, enter_permanent, resolve_stack


def _drain_pending():
    game = behavioral_game()
    player, opponent = game.players
    amulet = enter_permanent(game, player, RavenousAmulet())
    add_counter(game, amulet, "soul", 3)
    player.mana_pool.add(ManaType.COLORLESS, 4)
    activate_card_ability(game, player, amulet, 1)
    return game, player, opponent, amulet


class TestRavenousAmuletDrain:
    def test_each_opponent_loses_life_equal_to_its_soul_counters(self) -> None:
        game, player, opponent, amulet = _drain_pending()
        resolve_stack(game)
        assert opponent.life == 17
        assert not game.get_battlefield(player).contains(amulet)

    def test_uses_its_soul_counters_as_it_last_existed_if_it_left(self) -> None:
        game, _player, opponent, amulet = _drain_pending()
        exile(game, amulet)
        resolve_stack(game)
        assert opponent.life == 17
