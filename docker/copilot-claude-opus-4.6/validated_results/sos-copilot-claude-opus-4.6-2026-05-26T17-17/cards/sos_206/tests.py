"""Tests for SOS 206 — Nita, Forum Conciliator.

Legendary Creature — Human Advisor (2/3) {1}{W}{B}
- Whenever you cast a spell you don't own, put a +1/+1 counter on each creature you control.
- {2}, Sacrifice another creature: Exile target instant or sorcery card from an opponent's
  graveyard. You may cast it this turn, and mana of any type can be spent to cast that spell.
  If that spell would be put into a graveyard, exile it instead. Activate only as a sorcery.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_206.card_impl import NitaForumConciliator
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestNitaProperties:
    """Static card properties match the spec."""

    def test_name(self) -> None:
        card = NitaForumConciliator(owner=None)
        assert card.name == "Nita, Forum Conciliator"

    def test_mana_cost(self) -> None:
        card = NitaForumConciliator(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{W}{B}")

    def test_power_toughness(self) -> None:
        card = NitaForumConciliator(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 3

    def test_is_creature(self) -> None:
        card = NitaForumConciliator(owner=None)
        assert isinstance(card, Creature)

    def test_is_legendary(self) -> None:
        card = NitaForumConciliator(owner=None)
        assert card.legendary is True


class TestNitaCastTrigger:
    """Whenever you cast a spell you don't own, put +1/+1 on each creature you control."""

    def test_casting_owned_spell_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        nita = NitaForumConciliator(owner=p1, controller=p1)
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(nita)
        game.get_battlefield(p1).add(bear)

        # Simulate casting a spell that p1 owns
        owned_spell = Instant(name="Own Spell", owner=p1, controller=p1)
        nita.on_spell_cast(game, owned_spell)

        assert bear.plus_one_counters == 0

    def test_casting_opponent_spell_triggers_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        nita = NitaForumConciliator(owner=p1, controller=p1)
        bear = Creature(name="Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(nita)
        game.get_battlefield(p1).add(bear)

        # Simulate casting a spell that p2 owns (but p1 is casting)
        stolen_spell = Instant(name="Stolen Spell", owner=p2, controller=p1)
        nita.on_spell_cast(game, stolen_spell)

        assert bear.plus_one_counters == 1

    def test_trigger_puts_counter_on_all_controlled_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        nita = NitaForumConciliator(owner=p1, controller=p1)
        bear1 = Creature(name="Bear 1", owner=p1, controller=p1, base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear 2", owner=p1, controller=p1, base_power=3, base_toughness=3)
        game.get_battlefield(p1).add(nita)
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p1).add(bear2)

        stolen_spell = Instant(name="Stolen Spell", owner=p2, controller=p1)
        nita.on_spell_cast(game, stolen_spell)

        # All creatures including Nita get a counter
        assert nita.plus_one_counters == 1
        assert bear1.plus_one_counters == 1
        assert bear2.plus_one_counters == 1


class TestNitaActivatedAbility:
    """Sacrifice another creature to exile and cast instant/sorcery from opponent's GY."""

    def test_ability_exiles_target_from_opponent_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        nita = NitaForumConciliator(owner=p1, controller=p1)
        sac_target = Creature(name="Fodder", owner=p1, controller=p1, base_power=1, base_toughness=1)
        game.get_battlefield(p1).add(nita)
        game.get_battlefield(p1).add(sac_target)

        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        game.get_graveyard(p2).add(target_spell)

        nita.activate_ability(game, sacrifice=sac_target, target=target_spell)

        # The target spell should be exiled from the graveyard
        assert target_spell not in game.get_graveyard(p2).get_all()
        assert target_spell.zone == Zone.EXILE

    def test_ability_requires_sacrifice_of_another_creature(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        nita = NitaForumConciliator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(nita)

        target_spell = Instant(name="Lightning Bolt", owner=p2, controller=p2)
        game.get_graveyard(p2).add(target_spell)

        # Cannot sacrifice Nita itself — needs "another creature"
        with pytest.raises(Exception):
            nita.activate_ability(game, sacrifice=nita, target=target_spell)

    def test_ability_only_targets_instant_or_sorcery(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        nita = NitaForumConciliator(owner=p1, controller=p1)
        sac_target = Creature(name="Fodder", owner=p1, controller=p1, base_power=1, base_toughness=1)
        game.get_battlefield(p1).add(nita)
        game.get_battlefield(p1).add(sac_target)

        # A creature card in the opponent's graveyard should not be a valid target
        creature_card = Creature(name="Dead Bear", owner=p2, controller=p2, base_power=2, base_toughness=2)
        game.get_graveyard(p2).add(creature_card)

        with pytest.raises(Exception):
            nita.activate_ability(game, sacrifice=sac_target, target=creature_card)
