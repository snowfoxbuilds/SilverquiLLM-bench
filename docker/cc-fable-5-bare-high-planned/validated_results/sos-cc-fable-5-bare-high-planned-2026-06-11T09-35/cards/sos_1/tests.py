"""Tests for SOS 1 — The Dawning Archaic."""

from __future__ import annotations

from cards.sos.sos_1.card_impl import TheDawningArchaic
from engine.card import Instant, Sorcery
from engine.casting import resolve_top
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, declare_attackers, set_board_state


class _LifeZap(Instant):
    """Test instant: you gain 2 life."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Life Zap")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 2


def _resolve_all(game):
    while not game.stack.is_empty():
        resolve_top(game)


def _attack_ready(card):
    card.summoning_sick = False
    return card


class TestDawningArchaicStatic:
    def test_card_data(self):
        card = TheDawningArchaic(owner=None)
        assert card.name == "The Dawning Archaic"
        assert card.base_power == 7 and card.base_toughness == 7
        assert Keyword.REACH in card.keywords
        assert card.mana_cost == ManaCost.parse("{10}")


class TestDawningArchaicCostReduction:
    def test_reduced_by_graveyard_instants_and_sorceries(self):
        """3 instant/sorcery cards in graveyard → castable for {7}."""
        from test_utils import cast_spell

        game = create_game()
        p1 = game.players[0]
        gy = [_LifeZap(), Sorcery(name="Filler Sorcery"), _LifeZap()]
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, hand=[archaic], graveyard=gy,
                        mana={ManaType.COLORLESS: 7})
        cast_spell(game, 0, "The Dawning Archaic")
        assert p1.zones[Zone.BATTLEFIELD].contains(archaic)
        assert p1.mana_pool.total() == 0

    def test_no_reduction_with_empty_graveyard(self):
        from engine.casting import CastingError, cast_spell as engine_cast

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        set_board_state(game, 0, hand=[archaic], mana={ManaType.COLORLESS: 9})
        game.active_player_index = 0
        try:
            engine_cast(game, p1, archaic)
            cast_ok = True
        except CastingError:
            cast_ok = False
        assert not cast_ok, "9 mana must not pay {10} with empty graveyard"


class TestDawningArchaicAttackTrigger:
    def test_attack_casts_sole_graveyard_spell_then_exiles_it(self):
        game = create_game()
        p1 = game.players[0]
        archaic = _attack_ready(TheDawningArchaic(owner=None))
        zap = _LifeZap()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[zap])
        archaic.register_triggers(game)
        archaic.register_replacement_effects(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_all(game)

        assert p1.life == 22, "Life Zap should have resolved"
        assert p1.zones[Zone.EXILE].contains(zap), "spell exiled instead"
        assert not p1.zones[Zone.GRAVEYARD].contains(zap)

    def test_attack_with_empty_graveyard_does_nothing(self):
        game = create_game()
        p1 = game.players[0]
        archaic = _attack_ready(TheDawningArchaic(owner=None))
        set_board_state(game, 0, battlefield=[archaic])
        archaic.register_triggers(game)
        archaic.register_replacement_effects(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_all(game)

        assert p1.life == 20
        assert len(p1.zones[Zone.EXILE]) == 0

    def test_multiple_candidates_uses_choice_and_may_decline(self):
        """With two candidates the controller chooses; None declines."""
        game = create_game(scripts=([None], []))
        p1 = game.players[0]
        archaic = _attack_ready(TheDawningArchaic(owner=None))
        zap1, zap2 = _LifeZap(), _LifeZap()
        set_board_state(game, 0, battlefield=[archaic], graveyard=[zap1, zap2])
        archaic.register_triggers(game)
        archaic.register_replacement_effects(game)

        declare_attackers(game, ["The Dawning Archaic"])
        _resolve_all(game)

        assert p1.life == 20, "declined — no spell cast"
        assert len(p1.zones[Zone.GRAVEYARD]) == 2

    def test_normally_cast_spell_still_goes_to_graveyard(self):
        """The exile-instead clause applies only to trigger-cast spells."""
        from test_utils import cast_spell

        game = create_game()
        p1 = game.players[0]
        archaic = TheDawningArchaic(owner=None)
        zap = _LifeZap()
        set_board_state(game, 0, battlefield=[archaic], hand=[zap],
                        mana={ManaType.COLORLESS: 1})
        archaic.register_triggers(game)
        archaic.register_replacement_effects(game)

        cast_spell(game, 0, "Life Zap")

        assert p1.zones[Zone.GRAVEYARD].contains(zap)
        assert not p1.zones[Zone.EXILE].contains(zap)
