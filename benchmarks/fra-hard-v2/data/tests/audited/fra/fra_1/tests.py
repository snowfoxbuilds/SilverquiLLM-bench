"""Emrakul, the Exigent Doom, played at the table.

Each test builds a position, plays it through both players' scripts and judges
Emrakul by what the players can see: where Emrakul is, which lands are tapped,
what the granted mana pays for, which spells the rules allow, and combat.
"""

from card_impl import (
    EmrakulTheExigentDoom,
    EmrakulTheExigentDoomAbility1,
    EmrakulTheExigentDoomAbility4,
    EmrakulTheExigentDoomAbility5,
)
from cards.fdn.fdn_95.card_impl import SowerOfChaos, SowerOfChaosAbility1
from cards.fdn.fdn_122.card_impl import (
    KykarZephyrAwakener,
    KykarZephyrAwakenerAbility2,
    KykarZephyrAwakenerAbility3,
)
from cards.fdn.fdn_130.card_impl import QuickDrawKatana
from cards.fdn.fdn_146.card_impl import SavannahLions
from cards.fdn.fdn_153.card_impl import EssenceScatter
from cards.fdn.fdn_164.card_impl import SpectralSailor
from cards.fdn.fdn_175.card_impl import HerosDownfall
from cards.fdn.fdn_192.card_impl import BurstLightning
from cards.fdn.fdn_272.card_impl import Plains
from cards.fdn.fdn_274.card_impl import Island
from cards.fdn.fdn_276.card_impl import Swamp
from cards.fdn.fdn_278.card_impl import Mountain
from cards.fdn.fdn_280.card_impl import Forest, ForestAbility1
from cards.fdn.fdn_687.card_impl import DemolitionField, DemolitionFieldAbility2
from test_interface import Decision, ManaType, Phase, Side, Step, Zone, card, create_game, player

from silverquillm.table import Table, life, moves, off_stack, on_stack, taps, untaps

MAIN = (Phase.PRECOMBAT_MAIN, 0)
EXILE_ABILITY = EmrakulTheExigentDoomAbility5
GRANTED = EmrakulTheExigentDoomAbility5  # the "{T}: Add {C}{C}" the land gains
CAST_TRIGGER = EmrakulTheExigentDoomAbility1
WARD = EmrakulTheExigentDoomAbility4
FLICKER = Decision.mode(printed=KykarZephyrAwakenerAbility3)


def _asked_by(printed):
    """A ``per_query`` key: a question whose source is ``printed``'s object, so
    Kykar's questions are answered apart from the spell's own."""
    return lambda query: any(dict(source.attrs).get("printed") is printed for source in query.source)


def _library(n: int = 3) -> list:
    return [card(Plains) for _ in range(n)]


def _exile(t: Table, emrakul, land) -> None:
    """Player 0 pays {3} and exiles Emrakul from hand, targeting ``land``; it resolves."""
    t.act(0, EXILE_ABILITY, choices=[land], then=[moves(emrakul, Zone.EXILE), on_stack(EXILE_ABILITY, 0)],
          note="exiling Emrakul is part of the cost")
    t.pass_(0)
    t.pass_(1, then=[off_stack(EXILE_ABILITY)])


def _tap(t: Table, seat: int, lands) -> None:
    for land in lands:
        t.act(seat, land, then=[taps(land)])


def _in_exile(lands: int = 8, *, seat1: Side | None = None):
    """Emrakul in hand with {3} to exile it, a Forest to target and ``lands`` more Forests."""
    emrakul, target = card(EmrakulTheExigentDoom), card(Forest)
    forests = [card(Forest) for _ in range(lands)]
    game = create_game(
        Side(hand=[emrakul], battlefield=[target, *forests], library=_library(), mana={ManaType.COLORLESS: 3}),
        seat1 or Side(library=_library()),
        start=MAIN,
    )
    return game, emrakul, target, forests


def _cast_from_exile(t: Table, emrakul, untapped) -> None:
    """Player 0 casts Emrakul from exile; its cast trigger untaps ``untapped``,
    then Emrakul resolves."""
    t.act(0, emrakul, then=[moves(emrakul, Zone.STACK), on_stack(CAST_TRIGGER, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(CAST_TRIGGER), *[untaps(land) for land in untapped]])
    t.pass_(0)
    t.pass_(1, then=[moves(emrakul, Zone.BATTLEFIELD)])


def test_exiling_is_a_cost_and_the_grant_waits_for_resolution():
    game, emrakul, target, _ = _in_exile(0)
    t = Table(game)
    t.act(0, EXILE_ABILITY, choices=[target], then=[moves(emrakul, Zone.EXILE), on_stack(EXILE_ABILITY, 0)])
    t.act_illegal(0, GRANTED, note="the land has no granted ability yet")
    t.pass_(0)
    t.pass_(1, then=[off_stack(EXILE_ABILITY)])
    t.act(0, GRANTED, then=[taps(target)])
    t.run()


def test_the_grant_is_in_addition_to_the_lands_own_ability():
    game, emrakul, target, _ = _in_exile(0)
    t = Table(game)
    _exile(t, emrakul, target)
    t.act(0, ForestAbility1, then=[taps(target)])
    t.run()


def test_granted_mana_pays_for_emrakul_and_casting_it_untaps_the_lands():
    """Eight Forests and the granted {C}{C} make exactly {10}: Emrakul is cast
    from exile, its cast trigger untaps every land, and the grant is gone."""
    game, emrakul, target, forests = _in_exile(8)
    t = Table(game)
    _exile(t, emrakul, target)
    t.act(0, GRANTED, then=[taps(target)])
    _tap(t, 0, forests)
    _cast_from_exile(t, emrakul, [target, *forests])
    t.act_illegal(0, GRANTED, note="casting Emrakul from exile ended the grant")
    t.run()


def test_without_the_grant_nine_lands_cannot_cast_emrakul():
    game, emrakul, target, forests = _in_exile(8)
    t = Table(game)
    _exile(t, emrakul, target)
    t.act(0, ForestAbility1, then=[taps(target)])
    _tap(t, 0, forests)
    t.act_illegal(0, emrakul, note="{9} cannot pay {10}")
    t.run()


def test_casting_emrakul_untaps_only_its_controllers_lands():
    emrakul = card(EmrakulTheExigentDoom)
    mine, theirs = card(Forest, tapped=True), card(Forest, tapped=True)
    game = create_game(
        Side(hand=[emrakul], battlefield=[mine], library=_library(), mana={ManaType.COLORLESS: 10}),
        Side(battlefield=[theirs], library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, emrakul, then=[moves(emrakul, Zone.STACK), on_stack(CAST_TRIGGER, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(CAST_TRIGGER), untaps(mine)], note="player 1's Forest stays tapped")
    t.pass_(0)
    t.pass_(1, then=[moves(emrakul, Zone.BATTLEFIELD)])
    t.run()


def test_countering_emrakul_does_not_counter_its_cast_trigger():
    emrakul, scatter = card(EmrakulTheExigentDoom), card(EssenceScatter)
    mine, islands = card(Forest, tapped=True), [card(Island), card(Island)]
    game = create_game(
        Side(hand=[emrakul], battlefield=[mine], library=_library(), mana={ManaType.COLORLESS: 10}),
        Side(hand=[scatter], battlefield=islands, library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, emrakul, then=[moves(emrakul, Zone.STACK), on_stack(CAST_TRIGGER, 0)])
    t.pass_(0)
    _tap(t, 1, islands)
    t.act(1, scatter, choices=[emrakul], then=[moves(scatter, Zone.STACK)])
    t.pass_(1)
    t.pass_(0, then=[moves(scatter, Zone.GRAVEYARD), moves(emrakul, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(CAST_TRIGGER), untaps(mine)])
    t.run()


def test_casting_from_exile_needs_sorcery_timing():
    game, emrakul, target, forests = _in_exile(8)
    t = Table(game)
    _exile(t, emrakul, target)
    t.pass_to(Step.UPKEEP, 1)
    t.pass_(1)
    t.act(0, GRANTED, then=[taps(target)])
    _tap(t, 0, forests)
    t.act_illegal(0, emrakul, note="it is the opponent's turn")
    t.run()


def test_the_grant_lasts_through_later_turns():
    game, emrakul, target, _ = _in_exile(0)
    t = Table(game)
    _exile(t, emrakul, target)
    t.pass_to(Phase.PRECOMBAT_MAIN, 0)
    t.act(0, GRANTED, then=[taps(target)], note="two turns later the land still has the grant")
    t.run()


def test_an_opponents_land_can_get_the_grant_but_not_the_permission():
    """The land may be player 1's: player 1 taps it for {C}{C} and casts
    Quick-Draw Katana with it, but may not cast Emrakul."""
    emrakul, theirs, katana = card(EmrakulTheExigentDoom), card(Forest), card(QuickDrawKatana)
    game = create_game(
        Side(hand=[emrakul], library=_library(), mana={ManaType.COLORLESS: 3}),
        Side(hand=[katana], battlefield=[theirs], library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _exile(t, emrakul, theirs)
    t.pass_to(Phase.PRECOMBAT_MAIN, 1)
    t.act(1, GRANTED, then=[taps(theirs)])
    t.act_illegal(1, emrakul)
    t.act(1, katana, then=[moves(katana, Zone.STACK)], note="{C}{C} pays the Katana's {2}")
    t.pass_(1)
    t.pass_(0, then=[moves(katana, Zone.BATTLEFIELD)])
    t.run()


def test_exiling_needs_three_mana():
    emrakul, target = card(EmrakulTheExigentDoom), card(Forest)
    game = create_game(
        Side(hand=[emrakul], battlefield=[target], library=_library(), mana={ManaType.COLORLESS: 2}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act_illegal(0, EXILE_ABILITY, choices=[target], note="Emrakul stays in hand")
    t.run()


def test_exiling_works_only_from_hand():
    emrakul, target = card(EmrakulTheExigentDoom), card(Forest)
    game = create_game(
        Side(battlefield=[emrakul, target], library=_library(), mana={ManaType.COLORLESS: 3}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act_illegal(0, EXILE_ABILITY, choices=[target])
    t.run()


def _ward_game(seat1_battlefield):
    emrakul, downfall = card(EmrakulTheExigentDoom), card(HerosDownfall)
    game = create_game(
        Side(battlefield=[emrakul], library=_library()),
        Side(hand=[downfall], battlefield=seat1_battlefield, library=_library(), mana={ManaType.BLACK: 3}),
        start=(Phase.PRECOMBAT_MAIN, 1),
    )
    return game, emrakul, downfall


def test_ward_counters_a_spell_whose_controller_cannot_pay():
    game, emrakul, downfall = _ward_game([card(Plains), card(Plains)])
    t = Table(game)
    t.act(1, downfall, choices=[emrakul], then=[moves(downfall, Zone.STACK), on_stack(WARD, 0)])
    t.pass_(1, choices=[Decision.yes()])
    t.pass_(0, then=[off_stack(WARD), moves(downfall, Zone.GRAVEYARD)], note="willing or not, two permanents cannot pay ward")
    t.run()


def test_ward_is_paid_by_sacrificing_three_permanents():
    paid = [card(Plains), card(Plains), card(Plains)]
    game, emrakul, downfall = _ward_game(paid)
    t = Table(game)
    t.act(1, downfall, choices=[emrakul], then=[moves(downfall, Zone.STACK), on_stack(WARD, 0)])
    t.pass_(1, choices=[Decision.yes(), *paid])
    t.pass_(0, then=[off_stack(WARD), *[moves(land, Zone.GRAVEYARD) for land in paid]])
    t.pass_(1)
    t.pass_(0, then=[moves(downfall, Zone.GRAVEYARD), moves(emrakul, Zone.GRAVEYARD)])
    t.run()


def test_ward_may_be_declined():
    game, emrakul, downfall = _ward_game([card(Plains), card(Plains), card(Plains)])
    t = Table(game)
    t.act(1, downfall, choices=[emrakul], then=[moves(downfall, Zone.STACK), on_stack(WARD, 0)])
    t.pass_(1, choices=[Decision.no()])
    t.pass_(0, then=[off_stack(WARD), moves(downfall, Zone.GRAVEYARD)])
    t.run()


def test_its_controllers_own_spell_does_not_trigger_ward():
    emrakul, downfall = card(EmrakulTheExigentDoom), card(HerosDownfall)
    game = create_game(
        Side(hand=[downfall], battlefield=[emrakul], library=_library(), mana={ManaType.BLACK: 3}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, downfall, choices=[emrakul], then=[moves(downfall, Zone.STACK)])
    t.pass_(0)
    t.pass_(1, then=[moves(downfall, Zone.GRAVEYARD), moves(emrakul, Zone.GRAVEYARD)])
    t.run()


def test_emrakul_flies_and_tramples_as_a_twelve_twelve():
    """A ground creature cannot block Emrakul; a 1/1 flier can, and 11 tramples over."""
    emrakul, lions, sailor = card(EmrakulTheExigentDoom), card(SavannahLions), card(SpectralSailor)
    game = create_game(
        Side(battlefield=[emrakul], library=_library()),
        Side(battlefield=[lions, sailor], library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.pass_to(Step.DECLARE_ATTACKERS, 0)
    t.act(0, emrakul, then=[taps(emrakul)])
    t.pass_(0)
    t.pass_(1)
    t.act_illegal(1, lions, scoped={lions: [emrakul]}, note="Lions cannot block a flier")
    t.act(1, sailor, scoped={sailor: [emrakul]})
    t.pass_(0, choices=[Decision.number(1)])
    t.pass_(1, then=[moves(sailor, Zone.GRAVEYARD), life(1, 9)])
    t.run()


def test_exiling_with_swamps_also_works():
    """The {3} is generic: any mana pays it."""
    emrakul, target = card(EmrakulTheExigentDoom), card(Forest)
    swamps = [card(Swamp) for _ in range(3)]
    game = create_game(
        Side(hand=[emrakul], battlefield=[target, *swamps], library=_library()),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    _tap(t, 0, swamps)
    _exile(t, emrakul, target)
    t.act(0, GRANTED, then=[taps(target)])
    t.run()


def test_an_emrakul_exiled_some_other_way_cannot_be_cast():
    """Only exiling Emrakul with its own ability lets it be cast from exile."""
    emrakul = card(EmrakulTheExigentDoom)
    game = create_game(
        Side(exile=[emrakul], library=_library(), mana={ManaType.COLORLESS: 10}),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act_illegal(0, emrakul)
    t.run()


def test_a_target_land_destroyed_in_response_leaves_emrakul_uncastable_in_exile():
    """Player 1's Demolition Field destroys the targeted land in response: the
    exile ability's only target is gone, so it does nothing (rule 608.2b) — no
    mana grant and no permission to cast Emrakul — though Emrakul stays exiled,
    since exiling it was the cost."""
    emrakul, target = card(EmrakulTheExigentDoom), card(DemolitionField)
    field, plains = card(DemolitionField), [card(Plains), card(Plains)]
    game = create_game(
        Side(hand=[emrakul], battlefield=[target], library=[SavannahLions] * 3,
             mana={ManaType.COLORLESS: 13}),
        Side(battlefield=[field, *plains], library=[SavannahLions] * 3),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, EXILE_ABILITY, choices=[target], then=[moves(emrakul, Zone.EXILE), on_stack(EXILE_ABILITY, 0)])
    t.pass_(0)
    _tap(t, 1, plains)
    t.act(1, DemolitionFieldAbility2, choices=[target],
          then=[moves(field, Zone.GRAVEYARD), on_stack(DemolitionFieldAbility2, 1)])
    t.pass_(1)
    t.pass_(0, then=[off_stack(DemolitionFieldAbility2), moves(target, Zone.GRAVEYARD)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(EXILE_ABILITY)])
    t.act_illegal(0, emrakul, note="13 mana, but no permission to cast Emrakul from exile")
    t.run()


def test_emrakul_entering_without_being_cast_untaps_nothing():
    """Kykar exiles Emrakul and returns it at the next end step: Emrakul enters
    without being cast, so its cast trigger does not untap the tapped
    Mountain."""
    emrakul, kykar, mountain, bolt = (card(EmrakulTheExigentDoom), card(KykarZephyrAwakener), card(Mountain),
                                      card(BurstLightning))
    game = create_game(
        Side(hand=[bolt], battlefield=[emrakul, kykar, mountain], library=_library()),
        Side(library=_library()),
        start=MAIN,
    )
    t = Table(game)
    t.act(0, mountain, then=[taps(mountain)])
    kykar_asks = {_asked_by(KykarZephyrAwakener): [FLICKER, emrakul]}
    t.act(0, bolt, choices=[player(1)], per_query=kykar_asks,
          then=[moves(bolt, Zone.STACK), on_stack(KykarZephyrAwakenerAbility2, 0)])
    t.pass_(0, choices=[FLICKER, emrakul])
    t.pass_(1, then=[off_stack(KykarZephyrAwakenerAbility2), moves(emrakul, Zone.EXILE)])
    t.pass_(0)
    t.pass_(1, then=[moves(bolt, Zone.GRAVEYARD), life(1, 18)])
    t.pass_to(Phase.POSTCOMBAT_MAIN, 0)
    t.pass_(0)
    t.pass_(1, then=[on_stack(KykarZephyrAwakenerAbility3, 0)])
    t.pass_(0)
    t.pass_(1, then=[off_stack(KykarZephyrAwakenerAbility3), moves(emrakul, Zone.BATTLEFIELD)],
            note="the Mountain stays tapped")
    t.run()


def _sower_game():
    emrakul, sower = card(EmrakulTheExigentDoom), card(SowerOfChaos)
    mountains = [card(Mountain) for _ in range(3)]
    game = create_game(
        Side(battlefield=[emrakul], library=_library()),
        Side(battlefield=[sower, *mountains], library=_library()),
        start=(Phase.PRECOMBAT_MAIN, 1),
    )
    return game, emrakul, sower, mountains


def test_ward_counters_an_opponents_activated_ability_unless_paid():
    """Player 1 declines to sacrifice three permanents: the Sower's ability is
    countered, so Emrakul still blocks — and kills — the Sower."""
    game, emrakul, sower, mountains = _sower_game()
    t = Table(game)
    _tap(t, 1, mountains)
    t.act(1, SowerOfChaosAbility1, choices=[emrakul], then=[on_stack(SowerOfChaosAbility1, 1), on_stack(WARD, 0)])
    t.pass_(1, choices=[Decision.no()])
    t.pass_(0, then=[off_stack(WARD), off_stack(SowerOfChaosAbility1)])
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, sower, then=[taps(sower)])
    t.pass_(1)
    t.pass_(0)
    t.act(0, emrakul, scoped={emrakul: sower})
    t.pass_(1)
    t.pass_(0, then=[moves(sower, Zone.GRAVEYARD)])
    t.run()


def test_ward_paid_lets_the_opponents_activated_ability_resolve():
    """Player 1 sacrifices three permanents for ward: Emrakul cannot block this
    turn, and the Sower's 4 damage gets through."""
    game, emrakul, sower, mountains = _sower_game()
    t = Table(game)
    _tap(t, 1, mountains)
    t.act(1, SowerOfChaosAbility1, choices=[emrakul], then=[on_stack(SowerOfChaosAbility1, 1), on_stack(WARD, 0)])
    t.pass_(1, choices=[Decision.yes(), *mountains])
    t.pass_(0, then=[off_stack(WARD), *[moves(m, Zone.GRAVEYARD) for m in mountains]])
    t.pass_(1)
    t.pass_(0, then=[off_stack(SowerOfChaosAbility1)])
    t.pass_to(Step.DECLARE_ATTACKERS, 1)
    t.act(1, sower, then=[taps(sower)])
    t.pass_(1)
    t.pass_(0)
    t.act_illegal(0, emrakul, scoped={emrakul: sower}, note="Emrakul can't block this turn")
    t.pass_(0)
    t.pass_(1)
    t.pass_(0, then=[life(0, 16)])
    t.run()
