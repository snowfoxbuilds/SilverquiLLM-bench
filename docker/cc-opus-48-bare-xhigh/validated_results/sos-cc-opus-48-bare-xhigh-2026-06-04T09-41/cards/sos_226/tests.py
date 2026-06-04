"""Tests for Silverquill, the Disputant (SOS #226)."""

from __future__ import annotations

from collections import deque
from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Sorcery
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, TargetRequirement, Zone
from test_utils import cast_spell, create_game, set_board_state


def _is_creature(obj: Any) -> bool:
    return CardType.CREATURE in getattr(obj, "card_types", set())


class _Bolt(Sorcery):
    """Deals 2 damage to target creature."""

    def __init__(self) -> None:
        super().__init__(name="Test Bolt", mana_cost=ManaCost.parse("{1}"))

    def get_targets(self, game: Any) -> list[TargetRequirement]:
        return [TargetRequirement(_is_creature, "target creature", Zone.BATTLEFIELD)]

    def on_resolve(self, game: Any) -> None:
        from engine.game import deal_damage

        targets = getattr(self, "chosen_targets", []) or []
        if targets and targets[0] is not None:
            deal_damage(game, self, targets[0], 2)


def _sac_creature(name: str = "Goblin") -> Creature:
    return Creature(
        name=name,
        mana_cost=ManaCost.parse("{R}"),
        base_power=1,
        base_toughness=1,
    )


def test_basic_characteristics():
    card = SilverquillTheDisputant()
    assert card.base_power == 4 and card.base_toughness == 4
    assert Keyword.FLYING in card.keywords
    assert Keyword.VIGILANCE in card.keywords
    assert Supertype.LEGENDARY in card.supertypes


def test_grants_casualty_only_to_instants_and_sorceries():
    card = SilverquillTheDisputant()
    game = create_game()
    p1 = game.players[0]
    bolt = _Bolt()
    creature = _sac_creature()
    assert card.grants_casualty(game, bolt, p1) == 1
    assert card.grants_casualty(game, creature, p1) == 0


def test_casualty_copies_spell_when_paid():
    # p1 controls Silverquill + a sacrificeable creature; cast a bolt.
    game = create_game(scripts=([True, None], []))
    p1, p2 = game.players
    sil = SilverquillTheDisputant()
    goblin = _sac_creature()
    set_board_state(game, 0, battlefield=[sil, goblin])
    # Script the sac choice (goblin) after the yes decision.
    p1._script = deque([True, goblin])

    bolt = _Bolt()
    set_board_state(game, 0, hand=[bolt])
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    victim = Creature(name="Victim", mana_cost=ManaCost.parse("{1}"), base_power=0, base_toughness=8)
    set_board_state(game, 1, battlefield=[victim])

    cast_spell(game, 0, "Test Bolt", targets=[victim])

    # Original + copy each deal 2 → 4 total.
    assert victim.damage_marked == 4
    # Goblin was sacrificed.
    assert game.get_graveyard(p1).contains(goblin)
    assert not game.get_battlefield(p1).contains(goblin)


def test_casualty_declined_no_copy():
    game = create_game()
    p1, p2 = game.players
    sil = SilverquillTheDisputant()
    goblin = _sac_creature()
    set_board_state(game, 0, battlefield=[sil, goblin])
    # Decline casualty.
    p1._script = deque([False])

    bolt = _Bolt()
    set_board_state(game, 0, hand=[bolt])
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    victim = Creature(name="Victim", mana_cost=ManaCost.parse("{1}"), base_power=0, base_toughness=8)
    set_board_state(game, 1, battlefield=[victim])

    cast_spell(game, 0, "Test Bolt", targets=[victim])

    # No copy → only 2 damage; goblin survives.
    assert victim.damage_marked == 2
    assert game.get_battlefield(p1).contains(goblin)


def test_no_casualty_without_silverquill():
    # No grantor on the battlefield → casualty never offered (no script needed).
    game = create_game()
    p1, p2 = game.players
    goblin = _sac_creature()
    set_board_state(game, 0, battlefield=[goblin])
    bolt = _Bolt()
    set_board_state(game, 0, hand=[bolt])
    p1.mana_pool.add(ManaType.COLORLESS, 1)

    victim = Creature(name="Victim", mana_cost=ManaCost.parse("{1}"), base_power=0, base_toughness=8)
    set_board_state(game, 1, battlefield=[victim])

    cast_spell(game, 0, "Test Bolt", targets=[victim])
    assert victim.damage_marked == 2
