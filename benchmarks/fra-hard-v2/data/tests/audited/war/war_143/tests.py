"""Sarkhan the Masterless, played at the table.

Each test builds a position, plays it through both players' scripts and judges
Sarkhan by what the players can see: which loyalty abilities the rules allow, a
planeswalker attacking or dying as a 4/4 flying creature, a Dragon token
appearing, attackers dying before they deal damage, and life totals.
"""

from card_impl import (
    SarkhanTheMasterless,
    SarkhanTheMasterlessAbility1,
    SarkhanTheMasterlessAbility2,
    SarkhanTheMasterlessAbility3,
)
from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from cards.fdn.fdn_95.card_impl import SowerOfChaos
from cards.fdn.fdn_134.card_impl import (
    AjaniCallerOfThePride,
    AjaniCallerOfThePrideAbility1,
    AjaniCallerOfThePrideAbility2,
)
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_171.card_impl import DiregrafGhoul
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_197.card_impl import FirespitterWhelp
from cards.fdn.fdn_206.card_impl import ShivanDragon
from cards.fdn.fdn_227.card_impl import LlanowarElves
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_276.card_impl import Swamp
from test_interface import ManaType, Phase, Side, Step, Zone, card, create_game, player, token

from silverquillm.table import Table, appears, life, moves, off_stack, on_stack, taps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
PINGS = SarkhanTheMasterlessAbility1
ANIMATE = SarkhanTheMasterlessAbility2
DRAGON = SarkhanTheMasterlessAbility3


def _library(n: int = 4) -> list:
    return [Plains for _ in range(n)]


def _activate(t: Table, seat: int, ability, *, then=()) -> None:
    """``seat`` activates loyalty ability ``ability``; both pass and it resolves."""
    t.act(seat, ability, then=[on_stack(ability, seat)])
    t.pass_(seat)
    t.pass_(1 - seat, then=[off_stack(ability), *then])


def _attack_unblocked(t: Table, seat: int, *attackers, then=()) -> None:
    """At ``seat``'s declare attackers, ``attackers`` attack the other player,
    who blocks with nothing; ``then`` is what combat damage does."""
    t.pass_to(Step.DECLARE_ATTACKERS, seat)
    t.act(seat, *attackers, then=[taps(a) for a in attackers])
    t.pass_(seat)
    t.pass_(1 - seat)
    t.pass_(1 - seat)
    t.pass_(seat)
    t.pass_(1 - seat, then=list(then))


def _opponent_attacks(t: Table, *attackers, then=()) -> None:
    """Player 1 attacks player 0 with ``attackers``; Sarkhan's ability triggers
    for each and they resolve; ``then`` is what the last one does. Damage is
    not visible, so the order player 0 stacks them in does not show."""
    t.pass_to(Step.BEGIN_COMBAT, 1)
    t.pass_(1)
    t.pass_(0, choices=[PINGS for _ in attackers])
    t.act(1, *attackers, scoped={attacker: player(0) for attacker in attackers},
          then=[*[taps(a) for a in attackers], *[on_stack(PINGS, 0) for _ in attackers]])
    for n, _ in enumerate(attackers, 1):
        t.pass_(1)
        t.pass_(0, then=[off_stack(PINGS), *(then if n == len(attackers) else ())])


def _block(t: Table, blockers: dict, *, then=()) -> None:
    """In the declare blockers step player 0 blocks as ``blockers`` says; both
    pass to combat damage, which does ``then``."""
    t.pass_(1)
    t.pass_(0)
    t.act(0, *blockers, scoped=blockers)
    t.pass_(1)
    t.pass_(0, then=list(then))


def test_plus_one_makes_sarkhan_a_four_four_that_attacks():
    sarkhan = card(SarkhanTheMasterless)
    game = create_game(Side(battlefield=[sarkhan], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    _attack_unblocked(t, 0, sarkhan, then=[life(1, 16)])
    t.run()


def test_the_animated_planeswalker_flies():
    """A ground creature cannot block the flying Dragon."""
    sarkhan, lions = card(SarkhanTheMasterless), card(SavannahLions)
    game = create_game(Side(battlefield=[sarkhan], library=_library()),
                       Side(battlefield=[lions], library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, sarkhan, then=[taps(sarkhan)])
    t.pass_(0)
    t.pass_(1)
    t.act_illegal(1, lions, scoped={lions: sarkhan}, note="a non-flier cannot block a flier")
    t.pass_(1)
    t.pass_(0)
    t.pass_(1, then=[life(1, 16)])
    t.run()


def test_every_planeswalker_its_controller_controls_becomes_a_dragon():
    sarkhan, ajani = card(SarkhanTheMasterless), card(AjaniCallerOfThePride)
    game = create_game(Side(battlefield=[sarkhan, ajani], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    _attack_unblocked(t, 0, sarkhan, ajani, then=[life(1, 12)])
    t.run()


def test_an_animated_planeswalker_keeps_its_own_loyalty_abilities():
    """A Dragon Ajani is no planeswalker but keeps its abilities: its +1 puts a
    +1/+1 counter on itself, so it attacks for 5, and it still may activate
    only one loyalty ability a turn."""
    sarkhan, ajani = card(SarkhanTheMasterless), card(AjaniCallerOfThePride)
    game = create_game(Side(battlefield=[sarkhan, ajani], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    t.act(0, AjaniCallerOfThePrideAbility1, choices=[ajani], then=[on_stack(AjaniCallerOfThePrideAbility1, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(AjaniCallerOfThePrideAbility1)])
    t.act_illegal(0, AjaniCallerOfThePrideAbility2, choices=[ajani], note="Ajani has used its loyalty ability")
    _attack_unblocked(t, 0, ajani, then=[life(1, 15)])
    t.run()


def test_an_animated_planeswalker_dies_to_creature_removal():
    """As a 4/4 creature Sarkhan can be the target of "target creature", and 5
    damage destroys it; Fiery Annihilation exiles it instead."""
    sarkhan, annihilation = card(SarkhanTheMasterless), card(FieryAnnihilation)
    game = create_game(Side(battlefield=[sarkhan], library=_library()),
                       Side(hand=[annihilation], mana={ManaType.RED: 3}, library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    t.pass_(0)
    t.act(1, annihilation, choices=[sarkhan], then=[moves(annihilation, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(annihilation, Zone.GRAVEYARD), moves(sarkhan, Zone.EXILE)])
    t.run()


def test_the_dragons_stay_dragons_after_sarkhan_leaves():
    """Exiled after its +1 resolves, Sarkhan leaves Ajani a 4/4 flier for the
    turn (rule 611.2a)."""
    sarkhan, ajani, annihilation = card(SarkhanTheMasterless), card(AjaniCallerOfThePride), card(FieryAnnihilation)
    game = create_game(Side(battlefield=[sarkhan, ajani], library=_library()),
                       Side(hand=[annihilation], mana={ManaType.RED: 3}, library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    t.pass_(0)
    t.act(1, annihilation, choices=[sarkhan], then=[moves(annihilation, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(annihilation, Zone.GRAVEYARD), moves(sarkhan, Zone.EXILE)])
    _attack_unblocked(t, 0, ajani, then=[life(1, 16)])
    t.run()


def test_the_effect_ends_with_the_turn():
    """On the opponent's turn Sarkhan is no creature: "target creature" cannot
    take it."""
    sarkhan, annihilation = card(SarkhanTheMasterless), card(FieryAnnihilation)
    game = create_game(Side(battlefield=[sarkhan], library=_library()),
                       Side(hand=[annihilation], mana={ManaType.RED: 3}, library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    t.act_illegal(1, annihilation, choices=[sarkhan])
    t.run()


def test_plus_one_needs_no_other_planeswalker_and_leaves_creatures_alone():
    """A creature its controller controls is not a planeswalker and stays as it
    is: the Lions still attacks for 2."""
    sarkhan, lions = card(SarkhanTheMasterless), card(SavannahLions)
    game = create_game(Side(battlefield=[sarkhan, lions], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    _attack_unblocked(t, 0, lions, then=[life(1, 18)])
    t.run()


def test_minus_three_makes_a_four_four_flying_dragon_token():
    """The token cannot attack the turn it is made; next turn it attacks for 4.
    Sarkhan, at 2 loyalty, cannot −3 again but may +1."""
    sarkhan = card(SarkhanTheMasterless)
    game = create_game(Side(battlefield=[sarkhan], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, DRAGON, then=[appears(0)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.act_illegal(0, DRAGON, note="2 loyalty cannot pay −3")
    _activate(t, 0, ANIMATE)
    _attack_unblocked(t, 0, token(1), then=[life(1, 16)])
    t.run()


def test_starting_loyalty_pays_one_minus_three():
    """Five loyalty: −3 and, two turns later after a +1, −3 again leaves 0, and
    Sarkhan dies."""
    sarkhan = card(SarkhanTheMasterless)
    game = create_game(Side(battlefield=[sarkhan], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, DRAGON, then=[appears(0)])
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    _activate(t, 0, ANIMATE)
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.act(0, DRAGON, then=[on_stack(DRAGON, 0), moves(sarkhan, Zone.GRAVEYARD)], note="3 loyalty pays −3 and leaves 0")
    t.pass_(0)
    t.pass_(1, then=[off_stack(DRAGON), appears(0)])
    t.run()


def test_loyalty_abilities_once_per_turn():
    sarkhan = card(SarkhanTheMasterless)
    game = create_game(Side(battlefield=[sarkhan], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, ANIMATE)
    t.act_illegal(0, DRAGON)
    t.act_illegal(0, ANIMATE)
    t.run()


def test_loyalty_abilities_need_sorcery_timing():
    sarkhan = card(SarkhanTheMasterless)
    game = create_game(Side(battlefield=[sarkhan], library=_library()), Side(library=_library()),
                       start=(Phase.PRECOMBAT_MAIN, 1))
    t = Table(game)
    t.pass_(1)
    t.act_illegal(0, ANIMATE, note="it is the opponent's turn")
    t.run()


def test_a_dragons_ping_adds_to_combat_damage():
    """The Shivan Dragon deals 1 to the attacking Ghoul, so a 1/1 blocker's 1
    damage finishes it."""
    sarkhan, dragon, elves, ghoul = (card(SarkhanTheMasterless), card(ShivanDragon), card(LlanowarElves),
                                     card(DiregrafGhoul))
    game = create_game(Side(battlefield=[sarkhan, dragon, elves], library=_library()),
                       Side(battlefield=[ghoul], library=_library()), start=MAIN)
    t = Table(game)
    _opponent_attacks(t, ghoul)
    _block(t, {elves: ghoul}, then=[moves(elves, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)])
    t.run()


def test_no_dragon_no_damage():
    """With no Dragon the trigger does nothing: the Ghoul survives the 1/1
    blocker."""
    sarkhan, elves, ghoul = card(SarkhanTheMasterless), card(LlanowarElves), card(DiregrafGhoul)
    game = create_game(Side(battlefield=[sarkhan, elves], library=_library()),
                       Side(battlefield=[ghoul], library=_library()), start=MAIN)
    t = Table(game)
    _opponent_attacks(t, ghoul)
    _block(t, {elves: ghoul}, then=[moves(elves, Zone.GRAVEYARD)])
    t.run()


def test_each_dragon_deals_one_damage():
    """Two Dragons deal 2 to the 4/3 Sower; with a 1/1 blocker's 1 it dies."""
    sarkhan, shivan, whelp, elves, sower = (card(SarkhanTheMasterless), card(ShivanDragon), card(FirespitterWhelp),
                                            card(LlanowarElves), card(SowerOfChaos))
    game = create_game(Side(battlefield=[sarkhan, shivan, whelp, elves], library=_library()),
                       Side(battlefield=[sower], library=_library()), start=MAIN)
    t = Table(game)
    _opponent_attacks(t, sower)
    _block(t, {elves: sower}, then=[moves(elves, Zone.GRAVEYARD), moves(sower, Zone.GRAVEYARD)])
    t.run()


def test_one_dragon_is_one_damage():
    sarkhan, shivan, elves, sower = (card(SarkhanTheMasterless), card(ShivanDragon), card(LlanowarElves),
                                     card(SowerOfChaos))
    game = create_game(Side(battlefield=[sarkhan, shivan, elves], library=_library()),
                       Side(battlefield=[sower], library=_library()), start=MAIN)
    t = Table(game)
    _opponent_attacks(t, sower)
    _block(t, {elves: sower}, then=[moves(elves, Zone.GRAVEYARD)])
    t.run()


def test_an_attack_on_a_planeswalker_it_controls_triggers_too():
    """The Ghoul attacks Ajani, not player 0, and still takes the Dragon's 1."""
    sarkhan, ajani, dragon, elves, ghoul = (card(SarkhanTheMasterless), card(AjaniCallerOfThePride),
                                            card(ShivanDragon), card(LlanowarElves), card(DiregrafGhoul))
    game = create_game(Side(battlefield=[sarkhan, ajani, dragon, elves], library=_library()),
                       Side(battlefield=[ghoul], library=_library()), start=MAIN)
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, ghoul, scoped={ghoul: ajani}, then=[taps(ghoul), on_stack(PINGS, 0)])
    t.pass_(1)
    t.pass_(0, then=[off_stack(PINGS)])
    _block(t, {elves: ghoul}, then=[moves(elves, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)])
    t.run()


def test_each_attacker_triggers_it():
    """Two attackers, two triggers: the Dragon pings each Ghoul, and each dies
    to a 1/1 blocker."""
    sarkhan, dragon = card(SarkhanTheMasterless), card(ShivanDragon)
    elves, other_elves = card(LlanowarElves), card(LlanowarElves)
    ghoul, other_ghoul = card(DiregrafGhoul), card(DiregrafGhoul)
    game = create_game(Side(battlefield=[sarkhan, dragon, elves, other_elves], library=_library()),
                       Side(battlefield=[ghoul, other_ghoul], library=_library()), start=MAIN)
    t = Table(game)
    _opponent_attacks(t, ghoul, other_ghoul)
    _block(t, {elves: ghoul, other_elves: other_ghoul},
           then=[moves(elves, Zone.GRAVEYARD), moves(other_elves, Zone.GRAVEYARD),
                 moves(ghoul, Zone.GRAVEYARD), moves(other_ghoul, Zone.GRAVEYARD)])
    t.run()


def test_its_controllers_own_attack_does_not_trigger_it():
    sarkhan, dragon = card(SarkhanTheMasterless), card(ShivanDragon)
    game = create_game(Side(battlefield=[sarkhan, dragon], library=_library()), Side(library=_library()), start=MAIN)
    t = Table(game)
    _attack_unblocked(t, 0, dragon, then=[life(1, 15)])
    t.run()


def test_a_dragon_token_it_made_pings_attackers():
    """The −3 Dragon token is a Dragon its controller controls."""
    sarkhan, elves, ghoul = card(SarkhanTheMasterless), card(LlanowarElves), card(DiregrafGhoul)
    game = create_game(Side(battlefield=[sarkhan, elves], library=_library()),
                       Side(battlefield=[ghoul], library=_library()), start=MAIN)
    t = Table(game)
    _activate(t, 0, DRAGON, then=[appears(0)])
    _opponent_attacks(t, ghoul)
    _block(t, {elves: ghoul}, then=[moves(elves, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)])
    t.run()


def test_the_trigger_resolves_after_sarkhan_leaves():
    """Destroyed in response, Sarkhan's trigger still has the Dragon ping the
    attacker."""
    sarkhan, dragon, elves, ghoul, downfall = (card(SarkhanTheMasterless), card(ShivanDragon), card(LlanowarElves),
                                               card(DiregrafGhoul), card(HerosDownfall))
    swamps = [card(Swamp) for _ in range(3)]
    game = create_game(Side(battlefield=[sarkhan, dragon, elves], library=_library()),
                       Side(battlefield=[ghoul, *swamps], hand=[downfall], library=_library()),
                       start=(Step.BEGIN_COMBAT, 1))
    t = Table(game)
    t.pass_(1)
    t.pass_(0)
    t.act(1, ghoul, scoped={ghoul: player(0)}, then=[taps(ghoul), on_stack(PINGS, 0)])
    for swamp in swamps:
        t.act(1, swamp, then=[taps(swamp)])
    t.act(1, downfall, choices=[sarkhan], then=[moves(downfall, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(downfall, Zone.GRAVEYARD), moves(sarkhan, Zone.GRAVEYARD)])
    t.pass_(1)
    t.pass_(0, then=[off_stack(PINGS)])
    _block(t, {elves: ghoul}, then=[moves(elves, Zone.GRAVEYARD), moves(ghoul, Zone.GRAVEYARD)])
    t.run()
