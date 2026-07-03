"""Tests for Mana Sculpt (sos_57)."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import _resolve_top_of_stack, advance_to_phase, create_game


def _push_spell(game, player, card):
    """Push a spell directly onto the stack (simulating it being cast)."""
    so = StackObject(source=card, controller=player, on_resolve=lambda g: None)
    game.stack.push(so)
    return so


def _put_on_battlefield(game, player_index, card):
    p = game.players[player_index]
    card.owner = p
    card.controller = p
    p.zones[Zone.BATTLEFIELD].add(card)
    if hasattr(card, "register_triggers"):
        card.register_triggers(game)


class TestManaSculptProperties:
    def test_name(self) -> None:
        assert ManaSculpt().name == "Mana Sculpt"

    def test_is_instant(self) -> None:
        assert CardType.INSTANT in ManaSculpt().card_types


class TestCounterSpell:
    def test_counters_spell_to_graveyard(self) -> None:
        """Countered spell moves from stack to owner's graveyard."""
        game = create_game()
        p1, p2 = game.players

        target_card = Instant(name="Target", mana_cost=ManaCost.parse("{2}{U}"))
        target_card.owner = p2
        target_card.controller = p2
        target_so = _push_spell(game, p2, target_card)

        sculpt = ManaSculpt()
        sculpt.owner = p1
        sculpt.controller = p1
        sculpt.chosen_targets = [target_so]

        sculpt.on_resolve(game)

        assert game.get_graveyard(p2).contains(target_card)
        assert game.stack.is_empty()

    def test_no_mana_if_no_wizard_controlled(self) -> None:
        """No delayed mana trigger if controller has no Wizard."""
        game = create_game()
        p1, p2 = game.players

        target_card = Sorcery(name="BigSorcery", mana_cost=ManaCost.parse("{4}"))
        target_card.owner = p2
        target_card.controller = p2
        target_so = _push_spell(game, p2, target_card)

        sculpt = ManaSculpt()
        sculpt.owner = p1
        sculpt.controller = p1
        sculpt.chosen_targets = [target_so]

        sculpt.on_resolve(game)

        # Advance to next precombat main — no mana should be added
        game.active_player_index = 0
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_top_of_stack(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_delayed_mana_trigger_with_wizard(self) -> None:
        """With a Wizard on the battlefield, adds CMC colorless mana at next main phase."""
        game = create_game()
        p1, p2 = game.players

        # A 2/2 Wizard on p1's battlefield
        wizard = Creature(name="Wizard", base_power=2, base_toughness=2)
        wizard.subtypes = {"Wizard"}
        _put_on_battlefield(game, 0, wizard)

        # Target spell with CMC 4
        target_card = Sorcery(name="BigSorcery", mana_cost=ManaCost.parse("{4}"))
        target_card.owner = p2
        target_card.controller = p2
        target_so = _push_spell(game, p2, target_card)

        sculpt = ManaSculpt()
        sculpt.owner = p1
        sculpt.controller = p1
        sculpt.chosen_targets = [target_so]

        # Counter the spell (registers delayed trigger)
        sculpt.on_resolve(game)

        # We should be in some non-main phase; advance to p1's precombat main
        game.active_player_index = 0
        if game.phase != Phase.PRECOMBAT_MAIN:
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        else:
            # Already in main phase; advance one full turn cycle to next main phase
            advance_to_phase(game, Phase.BEGINNING, Step.UNTAP)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        # Trigger fires and adds {C} equal to CMC 4
        _resolve_top_of_stack(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_trigger_fires_only_once(self) -> None:
        """The delayed trigger fires exactly once and then does not fire again."""
        game = create_game()
        p1, p2 = game.players

        wizard = Creature(name="Wizard2", base_power=1, base_toughness=1)
        wizard.subtypes = {"Wizard"}
        _put_on_battlefield(game, 0, wizard)

        target_card = Instant(name="Tiny", mana_cost=ManaCost.parse("{2}"))
        target_card.owner = p2
        target_card.controller = p2
        target_so = _push_spell(game, p2, target_card)

        sculpt = ManaSculpt()
        sculpt.owner = p1
        sculpt.controller = p1
        sculpt.chosen_targets = [target_so]

        sculpt.on_resolve(game)

        game.active_player_index = 0
        if game.phase != Phase.PRECOMBAT_MAIN:
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        else:
            advance_to_phase(game, Phase.BEGINNING)
            advance_to_phase(game, Phase.PRECOMBAT_MAIN)

        _resolve_top_of_stack(game)
        mana_after_first = p1.mana_pool.get(ManaType.COLORLESS)

        # Advance again — trigger should NOT fire a second time
        p1.mana_pool.empty()
        advance_to_phase(game, Phase.BEGINNING, Step.UNTAP)
        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        _resolve_top_of_stack(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0  # did not fire again
