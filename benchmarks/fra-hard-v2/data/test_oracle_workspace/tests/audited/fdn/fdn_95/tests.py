"""Reference test for FDN 95 — Sower of Chaos.

Canonical exemplar for a **targeted activated ability** on a creature: the
target is chosen at activation, the ability resolves, and the target can't
block this turn — seen when its block is refused.
"""

from __future__ import annotations

from cards.fdn.fdn_87.card_impl import GoblinBoarders
from cards.fdn.fdn_95.card_impl import SowerOfChaos, SowerOfChaosAbility1
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_171.card_impl import DiregrafGhoul
from engine.card import printed_class
from engine.types import ManaCost, ManaType
from test_interface import Phase, Side, Step, Zone, card, create_game

from silverquillm.table import Table, life, moves, off_stack, on_stack, taps

_RRR = {ManaType.RED: 3}


class TestSowerOfChaosProperties:
    def test_static_data(self):
        sower = SowerOfChaos(owner=None)
        assert printed_class(sower) is SowerOfChaos
        assert sower.mana_cost == ManaCost.parse("{3}{R}")
        assert (sower.base_power, sower.base_toughness) == (4, 3)
        assert "Devil" in sower.subtypes


class TestSowerOfChaosAbility:
    def _setup(self, *, theirs=1):
        sower, lions = card(SowerOfChaos), card(SavannahLions)
        ghouls = [card(DiregrafGhoul) for _ in range(theirs)]
        game = create_game(
            Side(battlefield=[sower, lions], mana=_RRR),
            Side(battlefield=ghouls),
            start=(Phase.PRECOMBAT_MAIN, 0),
        )
        return Table(game), sower, lions, ghouls

    def _activate(self, t, target):
        t.act(0, SowerOfChaosAbility1, choices=[target], then=[on_stack(SowerOfChaosAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(SowerOfChaosAbility1)])

    def _attack_with(self, t, attacker):
        t.pass_to(Step.DECLARE_ATTACKERS, 0)
        t.act(0, attacker, then=[taps(attacker)])
        t.pass_(0)
        t.pass_(1)

    def test_target_cant_block_after_resolution(self):
        t, _sower, lions, (ghoul,) = self._setup()
        self._activate(t, ghoul)
        self._attack_with(t, lions)
        t.act_illegal(1, ghoul, scoped={ghoul: lions}, note="the target can't block this turn")
        t.pass_(1)
        t.pass_(0)
        t.pass_(1, then=[life(1, 18)])
        t.run()

    def test_cost_is_paid(self):
        """{2}{R} empties a pool of three red: a second activation can't be paid."""
        t, _sower, _lions, (ghoul,) = self._setup()
        t.act(0, SowerOfChaosAbility1, choices=[ghoul], then=[on_stack(SowerOfChaosAbility1, 0)])
        t.act_illegal(0, SowerOfChaosAbility1, choices=[ghoul], note="no mana is left")
        t.pass_(0)
        t.run()

    def test_targets_creature_captured_on_stack(self):
        """Only the creature targeted can't block: the opponent's other
        creature still blocks."""
        t, _sower, lions, (target, other) = self._setup(theirs=2)
        self._activate(t, target)
        self._attack_with(t, lions)
        t.act_illegal(1, target, scoped={target: lions})
        t.act(1, other, scoped={other: lions})
        t.pass_(0)
        t.pass_(1, then=[moves(lions, Zone.GRAVEYARD), moves(other, Zone.GRAVEYARD)],
                note="the untargeted 2/2 blocks, and the two trade")
        t.run()

    def test_source_off_battlefield_rejected_before_cost(self):
        """Legality invariant: with the Sower in the graveyard its ability is
        not activated, and the three mana still cast Goblin Boarders."""
        sower, boarders = card(SowerOfChaos), card(GoblinBoarders)
        game = create_game(
            Side(graveyard=[sower], hand=[boarders], mana=_RRR), Side(), start=(Phase.PRECOMBAT_MAIN, 0)
        )
        t = Table(game)
        t.act_illegal(0, SowerOfChaosAbility1, note="the source is not on the battlefield")
        t.act(0, boarders, then=[moves(boarders, Zone.STACK)], note="no mana was spent")
        t.pass_(0)
        t.pass_(1, then=[moves(boarders, Zone.BATTLEFIELD)])
        t.run()

    def test_can_target_any_creature_including_own(self):
        """On the opponent's turn player 0 makes their own Sower unable to
        block, and the opponent's attacker gets through."""
        sower, ghoul = card(SowerOfChaos), card(DiregrafGhoul)
        game = create_game(
            Side(battlefield=[sower], mana=_RRR), Side(battlefield=[ghoul]), start=(Step.BEGIN_COMBAT, 1)
        )
        t = Table(game)
        t.pass_(1)
        t.act(0, SowerOfChaosAbility1, choices=[sower], then=[on_stack(SowerOfChaosAbility1, 0)])
        t.pass_(0)
        t.pass_(1, then=[off_stack(SowerOfChaosAbility1)])
        t.pass_(1)
        t.pass_(0)
        t.act(1, ghoul, then=[taps(ghoul)])
        t.pass_(1)
        t.pass_(0)
        t.act_illegal(0, sower, scoped={sower: ghoul}, note="the Sower can't block this turn")
        t.pass_(0)
        t.pass_(1)
        t.pass_(0, then=[life(0, 18)])
        t.run()
