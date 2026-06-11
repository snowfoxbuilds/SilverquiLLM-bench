"""Tests for SOS 35 — Stirring Hopesinger.

A 1/3 Bird Bard for {2}{W} with Flying, Lifelink.
Repartee — Whenever you cast an instant or sorcery spell that targets a creature,
put a +1/+1 counter on each creature you control.
"""

from __future__ import annotations

import pytest
from cards.sos.sos_35.card_impl import StirringHopesinger
from engine.card import Creature, Instant
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestStirringHopesingerProperties:
    """Static card data should match the SOS 35 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(StirringHopesinger(owner=None), Creature)

    def test_name(self) -> None:
        assert StirringHopesinger(owner=None).name == "Stirring Hopesinger"

    def test_mana_cost(self) -> None:
        assert StirringHopesinger(owner=None).mana_cost == ManaCost.parse("{2}{W}")

    def test_power_toughness(self) -> None:
        card = StirringHopesinger(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 3

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in StirringHopesinger(owner=None).keywords

    def test_has_lifelink(self) -> None:
        assert Keyword.LIFELINK in StirringHopesinger(owner=None).keywords


class TestStirringHopesingerRepartee:
    """Repartee: casting instant/sorcery targeting a creature gives +1/+1 counters."""

    def test_instant_targeting_creature_triggers_counters(self) -> None:
        """Casting an instant that targets a creature puts +1/+1 on each creature you control."""
        game = create_game()
        p1 = game.players[0]

        hopesinger = StirringHopesinger(owner=p1, controller=p1)
        hopesinger.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(hopesinger)

        bear = Creature(name="Grizzly Bears", base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        bear.card_types = {CardType.CREATURE}
        bear.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(bear)

        # Cast an instant that targets a creature
        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        bolt.chosen_targets = [bear]
        bolt.targets_creature = True

        before_hopesinger = hopesinger.plus_one_counters
        before_bear = bear.plus_one_counters

        game.trigger_spell_cast(p1, bolt)

        assert hopesinger.plus_one_counters == before_hopesinger + 1
        assert bear.plus_one_counters == before_bear + 1

    def test_sorcery_targeting_creature_triggers_counters(self) -> None:
        """Casting a sorcery that targets a creature also triggers repartee."""
        game = create_game()
        p1 = game.players[0]

        hopesinger = StirringHopesinger(owner=p1, controller=p1)
        hopesinger.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(hopesinger)

        target_creature = Creature(name="Target", base_power=1, base_toughness=1,
                                   owner=game.players[1], controller=game.players[1])
        target_creature.card_types = {CardType.CREATURE}
        target_creature.zone = Zone.BATTLEFIELD
        game.get_battlefield(game.players[1]).add(target_creature)

        from engine.card import Sorcery
        sorc = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        sorc.card_types = {CardType.SORCERY}
        sorc.chosen_targets = [target_creature]
        sorc.targets_creature = True

        before = hopesinger.plus_one_counters
        game.trigger_spell_cast(p1, sorc)

        assert hopesinger.plus_one_counters == before + 1

    def test_instant_not_targeting_creature_does_not_trigger(self) -> None:
        """A spell that doesn't target a creature should not trigger repartee."""
        game = create_game()
        p1 = game.players[0]

        hopesinger = StirringHopesinger(owner=p1, controller=p1)
        hopesinger.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(hopesinger)

        # Instant targeting a player, not a creature
        bolt = Instant(name="Lava Spike", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        bolt.chosen_targets = [game.players[1]]
        bolt.targets_creature = False

        before = hopesinger.plus_one_counters
        game.trigger_spell_cast(p1, bolt)

        assert hopesinger.plus_one_counters == before

    def test_opponent_spell_does_not_trigger(self) -> None:
        """Opponent casting a spell targeting a creature should not trigger your repartee."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]

        hopesinger = StirringHopesinger(owner=p1, controller=p1)
        hopesinger.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(hopesinger)

        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p1, controller=p1)
        bear.card_types = {CardType.CREATURE}
        bear.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(bear)

        bolt = Instant(name="Enemy Bolt", owner=p2, controller=p2)
        bolt.card_types = {CardType.INSTANT}
        bolt.chosen_targets = [bear]
        bolt.targets_creature = True

        before = hopesinger.plus_one_counters
        game.trigger_spell_cast(p2, bolt)

        assert hopesinger.plus_one_counters == before

    def test_counters_go_on_all_creatures_you_control(self) -> None:
        """All creatures controlled by the caster get +1/+1 counters."""
        game = create_game()
        p1 = game.players[0]

        hopesinger = StirringHopesinger(owner=p1, controller=p1)
        hopesinger.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(hopesinger)

        bear1 = Creature(name="Bear A", base_power=2, base_toughness=2,
                         owner=p1, controller=p1)
        bear1.card_types = {CardType.CREATURE}
        bear1.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(bear1)

        bear2 = Creature(name="Bear B", base_power=2, base_toughness=2,
                         owner=p1, controller=p1)
        bear2.card_types = {CardType.CREATURE}
        bear2.zone = Zone.BATTLEFIELD
        game.get_battlefield(p1).add(bear2)

        bolt = Instant(name="Test Bolt", owner=p1, controller=p1)
        bolt.card_types = {CardType.INSTANT}
        bolt.chosen_targets = [bear1]
        bolt.targets_creature = True

        game.trigger_spell_cast(p1, bolt)

        assert hopesinger.plus_one_counters >= 1
        assert bear1.plus_one_counters >= 1
        assert bear2.plus_one_counters >= 1
