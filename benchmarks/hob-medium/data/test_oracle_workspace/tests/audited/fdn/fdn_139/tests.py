"""Reference test for FDN 139 — Cathar Commando.

Demonstrates a **targeted activated ability** (Phase D pattern 2) whose cost
sacrifices the source. The artifact/enchantment target is chosen at activation
(before the sacrifice) via a Player Query (answered by an Intent), captured on
the stack, revalidated at resolution, and destroyed.
"""

from __future__ import annotations

import pytest

from cards.fdn.fdn_139.card_impl import CatharCommando
from engine.abilities import AbilityError
from engine.card import Artifact, Creature, Enchantment
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import activate_card_ability, create_game, resolve_stack, set_board_state


def _on_battlefield(game, obj):
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


def _activate_targeting(game, player, source, target):
    inst = game.refs.instance_id(target, Zone.BATTLEFIELD.value)
    player.start_intent("cathar", Intent(
        pattern=GameRef(card=frozenset({("name", source.name)})),
        preferences=(Decision.obj(instance=inst),),
    ))
    try:
        activate_card_ability(game, player, source)
    finally:
        player.end_intent("cathar")


class TestCatharCommandoProperties:
    def test_static_data(self):
        card = CatharCommando(owner=None)
        assert card.name == "Cathar Commando"
        assert card.mana_cost == ManaCost.parse("{1}{W}")
        assert (card.base_power, card.base_toughness) == (3, 1)
        assert {"Human", "Soldier"} <= card.subtypes
        assert Keyword.FLASH in card.keywords

    def test_has_one_targeted_ability(self):
        abilities = CatharCommando(owner=None).get_activated_abilities()
        assert len(abilities) == 1
        assert abilities[0].targeting is not None


class TestCatharCommandoAbility:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        cathar = CatharCommando(owner=p1, controller=p1)
        rock = Artifact(name="Signet", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[cathar], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[rock])
        return game, p1, p2, cathar, rock

    def test_destroys_target_artifact(self):
        game, p1, p2, cathar, rock = self._setup()
        _activate_targeting(game, p1, cathar, rock)
        resolve_stack(game)
        assert not _on_battlefield(game, rock)          # destroyed
        assert game.get_graveyard(p2).contains(rock)

    def test_source_is_sacrificed_as_cost(self):
        game, p1, p2, cathar, rock = self._setup()
        _activate_targeting(game, p1, cathar, rock)
        assert not _on_battlefield(game, cathar)         # sacrificed
        assert p1.mana_pool.total() == 0                 # {1} paid

    def test_target_captured_on_stack(self):
        game, p1, p2, cathar, rock = self._setup()
        _activate_targeting(game, p1, cathar, rock)
        top = game.stack.peek()
        assert top.targets == [rock]

    def test_can_target_enchantment(self):
        game = create_game()
        p1, p2 = game.players
        cathar = CatharCommando(owner=p1, controller=p1)
        aura = Enchantment(name="Pacifism", owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[cathar], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[aura])
        _activate_targeting(game, p1, cathar, aura)
        resolve_stack(game)
        assert game.get_graveyard(p2).contains(aura)

    def test_no_legal_target_rejected_before_cost(self):
        """Option-set invariant: only artifacts/enchantments are legal targets.
        With only a creature present there is no legal target, so activation is
        rejected before any cost (no sacrifice, no mana spent)."""
        game = create_game()
        p1, p2 = game.players
        cathar = CatharCommando(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[cathar], mana={ManaType.WHITE: 1})
        set_board_state(game, 1, battlefield=[bear])
        with pytest.raises(AbilityError):
            activate_card_ability(game, p1, cathar)
        assert _on_battlefield(game, cathar)             # not sacrificed
        assert p1.mana_pool.total() == 1                 # no mana spent
