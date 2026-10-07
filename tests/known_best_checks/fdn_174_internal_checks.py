"""Known-Best checks moved out of fdn_174's FDN Audited Tests: #169: Known-Best's Fake Your Own Death ends its granted ability with a visible end-step trigger,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from cards.fdn.fdn_62.card_impl import HungryGhoul
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_174.card_impl import FakeYourOwnDeath
from cards.fdn.fdn_272.card_impl import Plains
from engine.card import Creature
from engine.game import destroy
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game
from test_utils import (
    advance_game_to_phase,
    behavioral_game,
    cast_card,
    object_preference,
    prefer,
    put_on_battlefield,
    resolve_stack,
)

from table import Table, moves


def arrange(*, extra_mana=0, hand=(), battlefield=()):
    """Player 0's main phase: Fake Your Own Death is cast on Savannah Lions,
    and is left on the stack."""
    spell, lions, ghoul = card(FakeYourOwnDeath), card(SavannahLions), card(HungryGhoul)
    game = create_game(
        Side(
            hand=[spell, *hand],
            battlefield=[lions, ghoul, *battlefield],
            mana={ManaType.BLACK: 1, ManaType.COLORLESS: 1 + extra_mana},
        ),
        Side(library=[card(Plains)]),
        start=(Phase.PRECOMBAT_MAIN, 0),
    )
    t = Table(game)
    t.act(0, spell, choices=[lions], then=[moves(spell, Zone.STACK)])
    return t, spell, lions, ghoul


def _legacy_arrange():
    """Kept in the old form: Known-Best expires the granted ability with an
    end-step trigger of its own, which a rules-correct engine never puts on
    the stack, so this test cannot be played through the end step."""
    game = behavioral_game()
    player = game.players[0]
    target = put_on_battlefield(game, player, Creature(name="Bear", base_power=2, base_toughness=2))
    spell = FakeYourOwnDeath(owner=player)
    player.mana_pool.add(ManaType.BLACK, 1)
    player.mana_pool.add(ManaType.COLORLESS, 1)
    prefer(player, object_preference(game, target))
    cast_card(game, player, spell, resolve=True)
    return game, player, spell, target


def test_cleanup_removes_buff_and_death_return():
    game, player, _spell, target = _legacy_arrange()
    advance_game_to_phase(game, Phase.ENDING, Step.CLEANUP)
    resolve_stack(game)
    assert target.power == 2
    destroy(game, target)
    resolve_stack(game)
    assert game.get_graveyard(player).contains(target)
    assert not any(getattr(c, "is_token", False) for c in game.get_battlefield(player).get_all())
