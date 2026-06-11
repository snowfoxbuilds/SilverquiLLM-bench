"""Tests for Silverquill, the Disputant (sos_226)."""

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, TargetRequirement, Zone
from test_utils import create_game, set_board_state, cast_spell


class LifeGainInstant(Instant):
    def __init__(self, **kw):
        kw.setdefault("name", "Lifegain Trick")
        kw.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kw)

    def on_resolve(self, game):
        if self.controller is not None:
            self.controller.life += 1


class ZapInstant(Instant):
    """Deals 2 damage to any target."""

    def __init__(self, **kw):
        kw.setdefault("name", "Zap")
        kw.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kw)

    def get_targets(self, game):
        from engine.types import CardType
        return [TargetRequirement(
            filter_fn=lambda obj: hasattr(obj, "life")
            or CardType.CREATURE in getattr(obj, "card_types", set()),
            description="any target",
            zone=Zone.BATTLEFIELD,
        )]

    def on_resolve(self, game):
        from engine.game import deal_damage
        chosen = getattr(self, "chosen_targets", None)
        if chosen and chosen[0] is not None:
            deal_damage(game, self, chosen[0], 2)


def _setup(extra_creatures=()):
    game = create_game()
    sq = SilverquillTheDisputant()
    set_board_state(game, 0, battlefield=[sq, *extra_creatures])
    sq.register_triggers(game)
    return game


class TestSilverquillTheDisputant:
    def test_keywords(self):
        card = SilverquillTheDisputant()
        assert Keyword.FLYING in card.keywords
        assert Keyword.VIGILANCE in card.keywords

    def test_casualty_sacrifice_copies_spell(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _setup([bear])
        p0 = game.players[0]
        set_board_state(game, 0, hand=[LifeGainInstant()], mana={ManaType.COLORLESS: 1})
        # Re-place battlefield wiped by set_board_state? hand-only call keeps battlefield.
        p0._script.append(bear)  # casualty: sacrifice the bear
        cast_spell(game, 0, "Lifegain Trick")
        assert p0.life == 22  # original + copy
        assert game.get_graveyard(p0).contains(bear)

    def test_casualty_declined(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _setup([bear])
        p0 = game.players[0]
        set_board_state(game, 0, hand=[LifeGainInstant()], mana={ManaType.COLORLESS: 1})
        p0._script.append(None)  # decline casualty
        cast_spell(game, 0, "Lifegain Trick")
        assert p0.life == 21
        assert game.get_battlefield(p0).contains(bear)

    def test_no_eligible_creature_no_prompt(self):
        weakling = Creature(name="Weakling", base_power=0, base_toughness=1)
        game = _setup([weakling])
        p0 = game.players[0]
        set_board_state(game, 0, hand=[LifeGainInstant()], mana={ManaType.COLORLESS: 1})
        # Weakling (power 0) is not a candidate, but Silverquill itself
        # (power 4) is, so a prompt still occurs; decline it.
        p0._script.append(None)
        cast_spell(game, 0, "Lifegain Trick")
        assert p0.life == 21

    def test_copy_keeps_targets_when_not_changed(self):
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        game = _setup([bear])
        p0, p1 = game.players
        set_board_state(game, 0, hand=[ZapInstant()], mana={ManaType.COLORLESS: 1})
        # script order: target choice (appendleft by cast_spell), then casualty
        # choose_card, then choose_yes_no for new targets.
        p0._script.append(bear)   # sacrifice bear
        p0._script.append(False)  # keep same targets for the copy
        cast_spell(game, 0, "Zap", targets=[p1])
        assert p1.life == 16  # 2 from copy + 2 from original

    def test_opponent_spell_does_not_trigger(self):
        game = _setup([])
        p1 = game.players[1]
        set_board_state(game, 1, hand=[LifeGainInstant()], mana={ManaType.COLORLESS: 1})
        cast_spell(game, 1, "Lifegain Trick")  # no prompts; would raise if triggered
        assert p1.life == 21
