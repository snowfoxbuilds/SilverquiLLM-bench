"""Known-Best checks moved out of fdn_224's FDN Audited Tests: #169: Known-Best has no kicker, and never applies Gnarlid Colony's trample grant,
so they drive the engine directly and guard the Known-Best engine without
being graded against candidates (ADR-018)."""

from __future__ import annotations

from cards.fdn.fdn_224.card_impl import GnarlidColony
from engine.card import Creature
from engine.types import Keyword
from engine.types import Zone as EngineZone
from engine.zones import move_to_zone
from test_utils import create_game as legacy_game
from test_utils import set_board_state


class TestGnarlidColonyKickerEntry:
    """Kicker: enters with two +1/+1 counters if it was kicked (rule 614.1c)."""

    def test_kicked_enters_as_four_four(self) -> None:
        game = legacy_game()
        p1 = game.players[0]
        card = GnarlidColony(owner=p1, controller=p1)
        card.kicked = True
        set_board_state(game, 0, hand=[card])
        move_to_zone(game, card, EngineZone.HAND, EngineZone.BATTLEFIELD)
        assert card.plus_one_counters == 2
        assert card.power == 4
        assert card.toughness == 4


class TestGnarlidColonyContinuousEffect:
    """The previously-crashing get_continuous_effects path."""

    def test_grants_trample_to_creatures_with_counters(self) -> None:
        game = legacy_game()
        p1 = game.players[0]
        gnarlid = GnarlidColony(owner=p1, controller=p1)
        buffed = Creature(name="Beast", subtypes={"Beast"}, base_power=1, base_toughness=1)
        plain = Creature(name="Bear", subtypes={"Bear"}, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[gnarlid, buffed, plain])
        from engine.game import add_counter
        add_counter(game, buffed, "+1/+1", 1)

        for eff in gnarlid.get_continuous_effects():
            game.effect_manager.add(eff)
        game.effect_manager.apply_all(game)

        assert Keyword.TRAMPLE in buffed.keywords
        assert Keyword.TRAMPLE not in plain.keywords
