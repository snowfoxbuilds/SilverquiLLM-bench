"""Tests for SOS 224 — Scolding Administrator.

Creature — Dwarf Cleric, {W}{B}, 2/2
- Menace
- Repartee — Whenever you cast an instant or sorcery spell that targets a
  creature, put a +1/+1 counter on this creature.
- When this creature dies, if it had counters on it, put those counters on up
  to one target creature.
"""

from __future__ import annotations

from cards.sos.sos_224.card_impl import ScoldingAdministrator
from engine.card import Creature, Instant
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state


class TestScoldingAdministratorProperties:
    """Static card data should match the SOS 224 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(ScoldingAdministrator(owner=None), Creature)

    def test_name(self) -> None:
        assert ScoldingAdministrator(owner=None).name == "Scolding Administrator"

    def test_mana_cost(self) -> None:
        assert ScoldingAdministrator(owner=None).mana_cost == ManaCost.parse("{W}{B}")

    def test_power_toughness(self) -> None:
        card = ScoldingAdministrator(owner=None)
        assert card.base_power == 2
        assert card.base_toughness == 2

    def test_has_menace(self) -> None:
        card = ScoldingAdministrator(owner=None)
        assert Keyword.MENACE in card.keywords


class TestScoldingAdministratorRepartee:
    """Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, put a +1/+1 counter on this creature."""

    def test_gets_counter_on_targeted_spell(self) -> None:
        """Casting an instant/sorcery that targets a creature gives a counter."""
        game = create_game()
        p1 = game.players[0]
        admin = ScoldingAdministrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(admin)

        target = Creature(name="Target Bear", owner=p1, controller=p1,
                          base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(target)

        counters_before = admin.plus_one_counters
        # Simulate casting a targeted instant/sorcery
        admin.on_spell_cast_targeting_creature(game, target)
        assert admin.plus_one_counters == counters_before + 1

    def test_no_counter_on_nontargeted_spell(self) -> None:
        """A spell that does NOT target a creature should not trigger repartee."""
        game = create_game()
        p1 = game.players[0]
        admin = ScoldingAdministrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(admin)

        counters_before = admin.plus_one_counters
        # Simulate casting a non-targeted spell
        admin.on_spell_cast_no_creature_target(game)
        assert admin.plus_one_counters == counters_before

    def test_multiple_spells_accumulate_counters(self) -> None:
        """Each qualifying spell adds a counter."""
        game = create_game()
        p1 = game.players[0]
        admin = ScoldingAdministrator(owner=p1, controller=p1)
        game.get_battlefield(p1).add(admin)

        target = Creature(name="Target Bear", owner=p1, controller=p1,
                          base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(target)

        admin.on_spell_cast_targeting_creature(game, target)
        admin.on_spell_cast_targeting_creature(game, target)
        assert admin.plus_one_counters == 2


class TestScoldingAdministratorDiesTrigger:
    """When this creature dies, if it had counters on it, put those counters on
    up to one target creature."""

    def test_transfers_counters_on_death(self) -> None:
        """Dying with counters transfers them to a target creature."""
        game = create_game()
        p1 = game.players[0]
        admin = ScoldingAdministrator(owner=p1, controller=p1)
        admin.plus_one_counters = 3
        game.get_battlefield(p1).add(admin)

        target = Creature(name="Ally", owner=p1, controller=p1,
                          base_power=1, base_toughness=1)
        game.get_battlefield(p1).add(target)

        target_counters_before = target.plus_one_counters
        admin.on_death(game, chosen_target=target)
        assert target.plus_one_counters == target_counters_before + 3

    def test_no_transfer_without_counters(self) -> None:
        """Dying with zero counters does not transfer anything."""
        game = create_game()
        p1 = game.players[0]
        admin = ScoldingAdministrator(owner=p1, controller=p1)
        admin.plus_one_counters = 0
        game.get_battlefield(p1).add(admin)

        target = Creature(name="Ally", owner=p1, controller=p1,
                          base_power=1, base_toughness=1)
        game.get_battlefield(p1).add(target)

        admin.on_death(game, chosen_target=target)
        assert target.plus_one_counters == 0

    def test_dies_trigger_with_no_target_is_noop(self) -> None:
        """If no target is chosen (up to one), nothing happens."""
        game = create_game()
        p1 = game.players[0]
        admin = ScoldingAdministrator(owner=p1, controller=p1)
        admin.plus_one_counters = 2
        game.get_battlefield(p1).add(admin)

        # No target chosen — should not raise
        admin.on_death(game, chosen_target=None)
