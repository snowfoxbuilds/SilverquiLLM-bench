"""Reference test for FDN 86 — Fiery Annihilation.

A spell with a **dependent** optional target: "Exile up to one target Equipment
attached to *that creature*" — the Equipment target is legal only when attached
to the creature chosen for the first (required) target of the *same* cast.
Equipment on a different creature is never offered, the relationship is
revalidated at resolution, and the two targets resolve independently when only
one remains legal.

The tests equip the opponent's creatures during the opponent's main phase,
and player 0 answers with the instant there. The 5 damage kills a 0/5 Aegis
Turtle, which is exiled instead of dying, and a 5/6 Grappling Kraken survives
it until more damage that turn kills it, again into exile.
"""

from __future__ import annotations

from cards.fdn.fdn_39.card_impl import GrapplingKraken
from cards.fdn.fdn_86.card_impl import FieryAnnihilation
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_150.card_impl import AegisTurtle
from cards.fdn.fdn_174.card_impl import FakeYourOwnDeath, FakeYourOwnDeathAbility1
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_249.card_impl import AdventuringGear, AdventuringGearAbility2
from engine.types import ManaType, Zone
from test_interface import Phase, Side, card, create_game

from table import Table, appears, moves, off_stack, on_stack, taps

_SPELL_MANA = {ManaType.RED: 1, ManaType.COLORLESS: 2}


def _equipped_board(creatures, gear=(), *, hand1=(), mana1=None):
    """Player 1's main phase: ``creatures`` on their battlefield, and each
    ``(equipment, creature)`` of ``gear`` equipped in turn; player 1 then
    passes priority to player 0, who holds Fiery Annihilation."""
    spell = card(FieryAnnihilation)
    game = create_game(
        Side(hand=[spell], mana=_SPELL_MANA),
        Side(battlefield=[*creatures, *(eq for eq, _ in gear)], hand=list(hand1),
             mana=mana1 or {ManaType.COLORLESS: 2}),
        start=(Phase.PRECOMBAT_MAIN, 1),
    )
    t = Table(game)
    for eq, creature in gear:
        t.act(1, eq, choices=[creature], then=[on_stack(AdventuringGearAbility2, 1)])
        t.pass_(1)
        t.pass_(0, then=[off_stack(AdventuringGearAbility2)])
    t.pass_(1)
    return t, spell


def _two_equipped():
    c1, c2 = card(AegisTurtle), card(AegisTurtle)
    eq1, eq2 = card(AdventuringGear), card(AdventuringGear)
    t, spell = _equipped_board([c1, c2], [(eq1, c1), (eq2, c2)])
    return t, spell, c1, c2, eq1, eq2


class TestFieryAnnihilationTargets:
    def test_second_creatures_equipment_is_selected_independently(self):
        t, spell, _c1, c2, _eq1, eq2 = _two_equipped()
        t.act(0, spell, choices=[c2, eq2], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), moves(eq2, Zone.EXILE), moves(c2, Zone.EXILE)],
                note="the second Turtle and its own Equipment are exiled; the first's stay")
        t.run()

    def test_other_creatures_equipment_not_selected(self):
        """Preferring the other creature's Equipment cannot exile it — it is
        never a legal target, either not offered or offered and rejected, the
        spell then cast choosing no Equipment — so nothing is exiled beyond the
        damage."""
        t, spell, c1, _c2, _eq1, eq2 = _two_equipped()
        t.act(0, branches=[[spell, c1, eq2], [spell, c1]], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), moves(c1, Zone.EXILE)],
                note="the first Turtle is exiled; the other creature's Equipment stays")
        t.run()

    def test_chosen_equipment_exiled(self):
        t, spell, c1, _c2, eq1, _eq2 = _two_equipped()
        t.act(0, spell, choices=[c1, eq1], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), moves(eq1, Zone.EXILE), moves(c1, Zone.EXILE)])
        t.run()

    def test_creature_leaves_and_returns_takes_no_damage(self):
        """The creature target leaves and returns before resolution: a new
        object, so it takes no damage.

        In response, player 1 casts Fake Your Own Death on the Lions and
        then kills it with Burst Lightning; it returns tapped, and player 1
        makes a Treasure. (Known-Best still exiles an Equipment that was
        attached to the old object, so this test leaves Equipment out.)"""
        lions = card(SavannahLions)
        fake, bolt = card(FakeYourOwnDeath), card(BurstLightning)
        t, spell = _equipped_board(
            [lions], hand1=[fake, bolt], mana1={ManaType.BLACK: 1, ManaType.COLORLESS: 1, ManaType.RED: 1},
        )
        t.act(0, spell, choices=[lions], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.act(1, fake, choices=[lions], then=[moves(fake, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[moves(fake, Zone.GRAVEYARD)])
        t.act(1, bolt, choices=[lions], then=[moves(bolt, Zone.STACK)])
        t.pass_(1)
        t.pass_(0, then=[
            moves(bolt, Zone.GRAVEYARD), moves(lions, Zone.GRAVEYARD),
            on_stack(FakeYourOwnDeathAbility1, 1),
        ])
        t.pass_(1)
        t.pass_(0, then=[
            off_stack(FakeYourOwnDeathAbility1), moves(lions, Zone.BATTLEFIELD, seat=1), taps(lions),
            appears(1),
        ])
        t.pass_(1)
        t.pass_(0, then=[moves(spell, Zone.GRAVEYARD)], note="the returned 2/1 Lions takes no damage")
        t.run()

    def test_zero_equipment_remains_legal(self):
        """No Equipment on the board: the spell is castable and exiles no
        Equipment (the optional target is skipped); its 5 damage kills the 0/5
        Turtle, which is exiled instead of dying."""
        turtle = card(AegisTurtle)
        t, spell = _equipped_board([turtle])
        t.act(0, spell, choices=[turtle], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD), moves(turtle, Zone.EXILE)])
        t.run()


class TestFieryAnnihilationDamage:
    def test_five_damage_does_not_kill_a_six_toughness_creature(self):
        """The 5/6 Kraken survives the 5 damage."""
        kraken = card(GrapplingKraken)
        t, spell = _equipped_board([kraken])
        t.act(0, spell, choices=[kraken], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD)], note="the Kraken survives")
        t.run()

    def test_later_lethal_damage_that_turn_exiles_it(self):
        """With 5 damage marked, Burst Lightning's 2 more kill the 5/6 Kraken
        — 2 alone would not — and it is exiled instead of dying."""
        kraken, spell, bolt = card(GrapplingKraken), card(FieryAnnihilation), card(BurstLightning)
        game = create_game(
            Side(hand=[spell, bolt], mana={ManaType.RED: 2, ManaType.COLORLESS: 2}),
            Side(battlefield=[kraken]),
            start=(Phase.PRECOMBAT_MAIN, 1),
        )
        t = Table(game)
        t.pass_(1)
        t.act(0, spell, choices=[kraken], then=[moves(spell, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(spell, Zone.GRAVEYARD)], note="the Kraken survives 5")
        t.pass_(1)
        t.act(0, bolt, choices=[kraken], then=[moves(bolt, Zone.STACK)])
        t.pass_(0)
        t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), moves(kraken, Zone.EXILE)])
        t.run()
