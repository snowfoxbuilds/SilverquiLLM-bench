"""Tests for cards/foundations/global_enchantments.py — Batch 10 global enchantments.

Verifies:
- Each enchantment's metadata (name, mana cost, card_types).
- Anthem effects boosting creatures (+1/+1 and +1/+0 for attacking).
- Keyword-granting effects (trample via Garruk's Uprising).
- Triggered abilities firing correctly (upkeep, ETB, spell-cast).
- Static effects (Authority of the Consuls tapping opponent creatures).
- Effects stopping when enchantment is removed from battlefield.
- Banishing Light exile-until-leaves behavior.
- Vampiric Rites activated ability (sacrifice, gain life, draw).
- register_global_enchantments() registers all 10 cards.
"""

from __future__ import annotations

import pytest

from cards.foundations.global_enchantments import (
    AnthemOfChampions,
    AuthorityOfTheConsuls,
    BanishingLight,
    GarruksUprising,
    GoblinOriflamme,
    ImpactTremors,
    PainfulQuandary,
    PhyrexianArena,
    RiteOfTheDragoncaller,
    VampiricRites,
    register_global_enchantments,
)
from cards.registry import CardRegistry
from engine.card import CardImpl, Creature, Enchantment, GameObject
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, Phase, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(name: str = "TestPlayer") -> DeterministicPlayer:
    return DeterministicPlayer(name=name, script=[])


def _make_game(
    *,
    p1_battlefield: list | None = None,
    p2_battlefield: list | None = None,
) -> tuple[GameState, DeterministicPlayer, DeterministicPlayer]:
    GameObject.reset_id_counter()
    p1 = _make_player("P1")
    p2 = _make_player("P2")
    game = GameState(players=[p1, p2])
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    for obj in (p1_battlefield or []):
        obj.controller = p1
        obj.owner = p1
        game.get_battlefield(p1).add(obj)
    for obj in (p2_battlefield or []):
        obj.controller = p2
        obj.owner = p2
        game.get_battlefield(p2).add(obj)
    return game, p1, p2


def _make_creature(name: str = "Bear", power: int = 2, toughness: int = 2, **kw) -> Creature:
    return Creature(name=name, base_power=power, base_toughness=toughness, **kw)


def _place_enchantment(game, enchantment, player):
    """Place enchantment on battlefield, set ownership, call on_resolve & register_triggers."""
    enchantment.owner = player
    enchantment.controller = player
    game.get_battlefield(player).add(enchantment)
    enchantment.on_resolve(game)
    if hasattr(enchantment, "register_triggers"):
        enchantment.register_triggers(game)
    return enchantment


def _apply_effects(game):
    """Apply all continuous effects."""
    game.effect_manager.apply_all(game)


def _add_cards_to_library(player, n: int) -> list:
    """Add n dummy cards to a player's library and return them."""
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards


# ===================================================================
# ANTHEM OF CHAMPIONS
# ===================================================================


class TestAnthemOfChampions:
    def test_metadata(self):
        card = AnthemOfChampions()
        assert card.name == "Anthem of Champions"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{G}{W}")

    def test_boosts_own_creatures_plus_1_1(self):
        bear = _make_creature("Bear", 2, 2)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        anthem = _place_enchantment(game, AnthemOfChampions(), p1)
        _apply_effects(game)
        assert bear.base_power == 3
        assert bear.base_toughness == 3

    def test_does_not_boost_opponent_creatures(self):
        opp_bear = _make_creature("OppBear", 2, 2)
        game, p1, p2 = _make_game(p2_battlefield=[opp_bear])
        _place_enchantment(game, AnthemOfChampions(), p1)
        _apply_effects(game)
        assert opp_bear.base_power == 2
        assert opp_bear.base_toughness == 2

    def test_boosts_multiple_creatures(self):
        bear1 = _make_creature("Bear1", 2, 2)
        bear2 = _make_creature("Bear2", 3, 3)
        game, p1, p2 = _make_game(p1_battlefield=[bear1, bear2])
        _place_enchantment(game, AnthemOfChampions(), p1)
        _apply_effects(game)
        assert bear1.base_power == 3
        assert bear2.base_power == 4

    def test_effect_stops_when_enchantment_removed(self):
        bear = _make_creature("Bear", 2, 2)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        anthem = _place_enchantment(game, AnthemOfChampions(), p1)
        _apply_effects(game)
        assert bear.base_power == 3
        # Remove enchantment from battlefield
        game.get_battlefield(p1).remove(anthem)
        _apply_effects(game)
        # After removal, effect should not boost
        assert bear.base_power == 2


# ===================================================================
# GOBLIN ORIFLAMME
# ===================================================================


class TestGoblinOriflamme:
    def test_metadata(self):
        card = GoblinOriflamme()
        assert card.name == "Goblin Oriflamme"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_boosts_attacking_creatures(self):
        attacker = _make_creature("Goblin", 1, 1)
        attacker.is_attacking = True
        game, p1, p2 = _make_game(p1_battlefield=[attacker])
        _place_enchantment(game, GoblinOriflamme(), p1)
        _apply_effects(game)
        assert attacker.base_power == 2

    def test_does_not_boost_non_attacking_creatures(self):
        creature = _make_creature("Goblin", 1, 1)
        creature.is_attacking = False
        game, p1, p2 = _make_game(p1_battlefield=[creature])
        _place_enchantment(game, GoblinOriflamme(), p1)
        _apply_effects(game)
        assert creature.base_power == 1

    def test_does_not_boost_opponent_attacking_creatures(self):
        opp_attacker = _make_creature("OppGoblin", 1, 1)
        opp_attacker.is_attacking = True
        game, p1, p2 = _make_game(p2_battlefield=[opp_attacker])
        _place_enchantment(game, GoblinOriflamme(), p1)
        _apply_effects(game)
        assert opp_attacker.base_power == 1

    def test_only_boosts_power_not_toughness(self):
        attacker = _make_creature("Goblin", 1, 1)
        attacker.is_attacking = True
        game, p1, p2 = _make_game(p1_battlefield=[attacker])
        _place_enchantment(game, GoblinOriflamme(), p1)
        _apply_effects(game)
        assert attacker.base_toughness == 1  # unchanged


# ===================================================================
# GARRUK'S UPRISING
# ===================================================================


class TestGarruksUprising:
    def test_metadata(self):
        card = GarruksUprising()
        assert card.name == "Garruk's Uprising"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{2}{G}")

    def test_grants_trample_to_own_creatures(self):
        bear = _make_creature("Bear", 2, 2)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        _place_enchantment(game, GarruksUprising(), p1)
        _apply_effects(game)
        assert Keyword.TRAMPLE in bear.keywords or bear.keywords & Keyword.TRAMPLE

    def test_does_not_grant_trample_to_opponent(self):
        opp_bear = _make_creature("OppBear", 2, 2)
        game, p1, p2 = _make_game(p2_battlefield=[opp_bear])
        _place_enchantment(game, GarruksUprising(), p1)
        _apply_effects(game)
        assert not (opp_bear.keywords & Keyword.TRAMPLE)

    def test_etb_draws_card_if_power_4_creature(self):
        big = _make_creature("Giant", 5, 5)
        game, p1, p2 = _make_game(p1_battlefield=[big])
        _add_cards_to_library(p1, 3)
        hand_before = len(game.get_hand(p1).get_all())
        _place_enchantment(game, GarruksUprising(), p1)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before + 1

    def test_etb_no_draw_if_no_power_4_creature(self):
        small = _make_creature("Bear", 2, 2)
        game, p1, p2 = _make_game(p1_battlefield=[small])
        _add_cards_to_library(p1, 3)
        hand_before = len(game.get_hand(p1).get_all())
        _place_enchantment(game, GarruksUprising(), p1)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before

    def test_trigger_draws_on_power_4_creature_etb(self):
        game, p1, p2 = _make_game()
        _add_cards_to_library(p1, 5)
        uprising = _place_enchantment(game, GarruksUprising(), p1)
        hand_before = len(game.get_hand(p1).get_all())
        # Simulate a power-4 creature entering the battlefield
        big = _make_creature("Giant", 5, 5)
        big.controller = p1
        big.owner = p1
        game.get_battlefield(p1).add(big)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": big},
        )
        # Resolve any triggered abilities on the stack
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before + 1

    def test_trigger_no_draw_on_power_3_creature_etb(self):
        game, p1, p2 = _make_game()
        _add_cards_to_library(p1, 5)
        uprising = _place_enchantment(game, GarruksUprising(), p1)
        hand_before = len(game.get_hand(p1).get_all())
        small = _make_creature("Elf", 3, 3)
        small.controller = p1
        small.owner = p1
        game.get_battlefield(p1).add(small)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": small},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        hand_after = len(game.get_hand(p1).get_all())
        assert hand_after == hand_before


# ===================================================================
# AUTHORITY OF THE CONSULS
# ===================================================================


class TestAuthorityOfTheConsuls:
    def test_metadata(self):
        card = AuthorityOfTheConsuls()
        assert card.name == "Authority of the Consuls"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{W}")

    def test_opponent_creatures_enter_tapped(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, AuthorityOfTheConsuls(), p1)
        opp_creature = _make_creature("OppBear", 2, 2)
        opp_creature.controller = p2
        opp_creature.owner = p2
        opp_creature.summoning_sick = True
        game.get_battlefield(p2).add(opp_creature)
        _apply_effects(game)
        assert opp_creature.is_tapped is True

    def test_own_creatures_not_tapped(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, AuthorityOfTheConsuls(), p1)
        own_creature = _make_creature("MyBear", 2, 2)
        own_creature.controller = p1
        own_creature.owner = p1
        own_creature.summoning_sick = True
        game.get_battlefield(p1).add(own_creature)
        _apply_effects(game)
        assert own_creature.is_tapped is False

    def test_gains_life_on_opponent_creature_etb(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, AuthorityOfTheConsuls(), p1)
        life_before = p1.life
        opp_creature = _make_creature("OppBear", 2, 2)
        opp_creature.controller = p2
        opp_creature.owner = p2
        game.get_battlefield(p2).add(opp_creature)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": opp_creature},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p1.life == life_before + 1

    def test_no_life_gain_on_own_creature_etb(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, AuthorityOfTheConsuls(), p1)
        life_before = p1.life
        own_creature = _make_creature("MyBear", 2, 2)
        own_creature.controller = p1
        own_creature.owner = p1
        game.get_battlefield(p1).add(own_creature)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": own_creature},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p1.life == life_before


# ===================================================================
# PHYREXIAN ARENA
# ===================================================================


class TestPhyrexianArena:
    def test_metadata(self):
        card = PhyrexianArena()
        assert card.name == "Phyrexian Arena"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")

    def test_upkeep_trigger_draws_card_and_loses_life(self):
        game, p1, p2 = _make_game()
        _add_cards_to_library(p1, 5)
        _place_enchantment(game, PhyrexianArena(), p1)
        game.active_player_index = 0  # p1 is active
        hand_before = len(game.get_hand(p1).get_all())
        life_before = p1.life
        game.trigger_manager.fire_event(
            game,
            EventType.BEGINNING_OF_UPKEEP,
            {},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == hand_before + 1
        assert p1.life == life_before - 1

    def test_upkeep_does_not_trigger_on_opponents_turn(self):
        game, p1, p2 = _make_game()
        _add_cards_to_library(p1, 5)
        _place_enchantment(game, PhyrexianArena(), p1)
        game.active_player_index = 1  # p2 is active (opponent's turn)
        hand_before = len(game.get_hand(p1).get_all())
        life_before = p1.life
        game.trigger_manager.fire_event(
            game,
            EventType.BEGINNING_OF_UPKEEP,
            {},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert len(game.get_hand(p1).get_all()) == hand_before
        assert p1.life == life_before


# ===================================================================
# IMPACT TREMORS
# ===================================================================


class TestImpactTremors:
    def test_metadata(self):
        card = ImpactTremors()
        assert card.name == "Impact Tremors"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{1}{R}")

    def test_deals_1_damage_to_opponents_on_creature_etb(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, ImpactTremors(), p1)
        opp_life_before = p2.life
        creature = _make_creature("Goblin", 1, 1)
        creature.controller = p1
        creature.owner = p1
        game.get_battlefield(p1).add(creature)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": creature},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p2.life == opp_life_before - 1

    def test_does_not_trigger_on_opponent_creature_etb(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, ImpactTremors(), p1)
        opp_life_before = p2.life
        opp_creature = _make_creature("OppGoblin", 1, 1)
        opp_creature.controller = p2
        opp_creature.owner = p2
        game.get_battlefield(p2).add(opp_creature)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": opp_creature},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p2.life == opp_life_before

    def test_does_not_trigger_on_noncreature_etb(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, ImpactTremors(), p1)
        opp_life_before = p2.life
        artifact = CardImpl(name="SomeArtifact")
        artifact.card_types = {CardType.ARTIFACT}
        artifact.controller = p1
        artifact.owner = p1
        game.get_battlefield(p1).add(artifact)
        game.trigger_manager.fire_event(
            game,
            EventType.ENTERS_BATTLEFIELD,
            {"permanent": artifact},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p2.life == opp_life_before


# ===================================================================
# RITE OF THE DRAGONCALLER
# ===================================================================


class TestRiteOfTheDragoncaller:
    def test_metadata(self):
        card = RiteOfTheDragoncaller()
        assert card.name == "Rite of the Dragoncaller"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{4}{R}{R}")

    def test_creates_dragon_on_instant_cast(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, RiteOfTheDragoncaller(), p1)
        bf_before = len(game.get_battlefield(p1).get_all())
        # Simulate casting an instant spell
        spell = CardImpl(name="Lightning Bolt")
        spell.card_types = {CardType.INSTANT}
        spell.controller = p1
        game.trigger_manager.fire_event(
            game,
            EventType.SPELL_CAST,
            {"spell": spell},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf_after = game.get_battlefield(p1).get_all()
        assert len(bf_after) == bf_before + 1
        # Find the dragon token
        dragons = [o for o in bf_after if getattr(o, "name", "") == "Dragon"]
        assert len(dragons) >= 1
        dragon = dragons[0]
        assert dragon.base_power == 5
        assert dragon.base_toughness == 5
        assert Keyword.FLYING in dragon.keywords or dragon.keywords & Keyword.FLYING

    def test_creates_dragon_on_sorcery_cast(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, RiteOfTheDragoncaller(), p1)
        spell = CardImpl(name="Divination")
        spell.card_types = {CardType.SORCERY}
        spell.controller = p1
        game.trigger_manager.fire_event(
            game,
            EventType.SPELL_CAST,
            {"spell": spell},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        dragons = [o for o in bf if getattr(o, "name", "") == "Dragon"]
        assert len(dragons) >= 1

    def test_does_not_trigger_on_opponent_spell(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, RiteOfTheDragoncaller(), p1)
        spell = CardImpl(name="OppSpell")
        spell.card_types = {CardType.INSTANT}
        spell.controller = p2
        game.trigger_manager.fire_event(
            game,
            EventType.SPELL_CAST,
            {"spell": spell},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        dragons = [o for o in bf if getattr(o, "name", "") == "Dragon"]
        assert len(dragons) == 0

    def test_does_not_trigger_on_creature_spell(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, RiteOfTheDragoncaller(), p1)
        spell = CardImpl(name="Bear")
        spell.card_types = {CardType.CREATURE}
        spell.controller = p1
        game.trigger_manager.fire_event(
            game,
            EventType.SPELL_CAST,
            {"spell": spell},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        bf = game.get_battlefield(p1).get_all()
        dragons = [o for o in bf if getattr(o, "name", "") == "Dragon"]
        assert len(dragons) == 0


# ===================================================================
# PAINFUL QUANDARY
# ===================================================================


class TestPainfulQuandary:
    def test_metadata(self):
        card = PainfulQuandary()
        assert card.name == "Painful Quandary"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{3}{B}{B}")

    def test_opponent_loses_5_life_on_spell_cast(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, PainfulQuandary(), p1)
        opp_life_before = p2.life
        spell = CardImpl(name="OppSpell")
        spell.card_types = {CardType.INSTANT}
        spell.controller = p2
        game.trigger_manager.fire_event(
            game,
            EventType.SPELL_CAST,
            {"spell": spell},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p2.life == opp_life_before - 5

    def test_does_not_trigger_on_own_spell(self):
        game, p1, p2 = _make_game()
        _place_enchantment(game, PainfulQuandary(), p1)
        opp_life_before = p2.life
        own_life_before = p1.life
        spell = CardImpl(name="MySpell")
        spell.card_types = {CardType.INSTANT}
        spell.controller = p1
        game.trigger_manager.fire_event(
            game,
            EventType.SPELL_CAST,
            {"spell": spell},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        assert p2.life == opp_life_before
        assert p1.life == own_life_before


# ===================================================================
# BANISHING LIGHT
# ===================================================================


class TestBanishingLight:
    def test_metadata(self):
        card = BanishingLight()
        assert card.name == "Banishing Light"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{2}{W}")

    def test_exiles_opponent_nonland_permanent(self):
        opp_creature = _make_creature("OppBear", 2, 2)
        game, p1, p2 = _make_game(p2_battlefield=[opp_creature])
        banish = BanishingLight()
        banish.owner = p1
        banish.controller = p1
        banish.chosen_targets = [opp_creature]
        game.get_battlefield(p1).add(banish)
        banish.on_resolve(game)
        # Creature should be exiled (not on battlefield)
        bf_p2 = game.get_battlefield(p2).get_all()
        assert opp_creature not in bf_p2

    def test_returns_permanent_when_banishing_light_leaves(self):
        opp_creature = _make_creature("OppBear", 2, 2)
        game, p1, p2 = _make_game(p2_battlefield=[opp_creature])
        banish = BanishingLight()
        banish.owner = p1
        banish.controller = p1
        banish.chosen_targets = [opp_creature]
        game.get_battlefield(p1).add(banish)
        banish.on_resolve(game)
        banish.register_triggers(game)
        # Now remove banishing light — should return creature
        game.trigger_manager.fire_event(
            game,
            EventType.LEAVES_BATTLEFIELD,
            {"permanent": banish},
        )
        while not game.stack.is_empty():
            obj = game.stack.pop()
            obj.on_resolve(game)
        # Creature should be back on battlefield
        bf_all = game.get_battlefield(p2).get_all()
        assert opp_creature in bf_all

    def test_get_targets_returns_nonland_opponent_permanents(self):
        opp_creature = _make_creature("OppBear", 2, 2)
        game, p1, p2 = _make_game(p2_battlefield=[opp_creature])
        banish = BanishingLight()
        banish.owner = p1
        banish.controller = p1
        targets = banish.get_targets(game)
        assert len(targets) > 0

    def test_fizzles_if_target_not_on_battlefield(self):
        game, p1, p2 = _make_game()
        banish = BanishingLight()
        banish.owner = p1
        banish.controller = p1
        missing = _make_creature("Ghost", 1, 1)
        banish.chosen_targets = [missing]
        game.get_battlefield(p1).add(banish)
        # on_resolve should not crash even if target is gone
        banish.on_resolve(game)
        assert banish._exiled_card is None


# ===================================================================
# VAMPIRIC RITES
# ===================================================================


class TestVampiricRites:
    def test_metadata(self):
        card = VampiricRites()
        assert card.name == "Vampiric Rites"
        assert CardType.ENCHANTMENT in card.card_types
        assert card.mana_cost == ManaCost.parse("{B}")

    def test_has_activated_ability(self):
        card = VampiricRites()
        abilities = card.get_activated_abilities()
        assert len(abilities) >= 1

    def test_activated_ability_sacrifices_creature_gains_life_draws(self):
        """Vampiric Rites ability: sacrifice a creature, gain 1 life, draw a card.

        Note: The implementation calls sacrifice(game, obj) but the engine
        signature is sacrifice(game, player, permanent). This test verifies
        the intended behavior — if it fails with TypeError, the implementation
        has a bug in the sacrifice call.
        """
        bear = _make_creature("Bear", 2, 2)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        _add_cards_to_library(p1, 3)
        rites = _place_enchantment(game, VampiricRites(), p1)
        life_before = p1.life
        hand_before = len(game.get_hand(p1).get_all())
        abilities = rites.get_activated_abilities()
        ability = abilities[0]
        ability.effect(game)
        # Bear should be sacrificed (removed from battlefield)
        bf = game.get_battlefield(p1).get_all()
        assert bear not in bf
        # Should gain 1 life
        assert p1.life == life_before + 1
        # Should draw a card
        assert len(game.get_hand(p1).get_all()) == hand_before + 1

    def test_ability_cost_requires_creature(self):
        game, p1, p2 = _make_game()  # no creatures
        rites = _place_enchantment(game, VampiricRites(), p1)
        abilities = rites.get_activated_abilities()
        ability = abilities[0]
        assert ability.cost(game) is False

    def test_ability_cost_returns_true_with_creature(self):
        bear = _make_creature("Bear", 2, 2)
        game, p1, p2 = _make_game(p1_battlefield=[bear])
        rites = _place_enchantment(game, VampiricRites(), p1)
        abilities = rites.get_activated_abilities()
        ability = abilities[0]
        assert ability.cost(game) is True


# ===================================================================
# REGISTRATION
# ===================================================================


class TestRegistration:
    def test_register_all_ten_enchantments(self):
        registry = CardRegistry()
        register_global_enchantments(registry)
        expected_names = [
            "Anthem of Champions",
            "Goblin Oriflamme",
            "Garruk's Uprising",
            "Authority of the Consuls",
            "Phyrexian Arena",
            "Impact Tremors",
            "Rite of the Dragoncaller",
            "Painful Quandary",
            "Banishing Light",
            "Vampiric Rites",
        ]
        for name in expected_names:
            assert registry.get(name) is not None, f"{name} not registered"

    def test_registered_classes_are_correct(self):
        registry = CardRegistry()
        register_global_enchantments(registry)
        class_map = {
            "Anthem of Champions": AnthemOfChampions,
            "Goblin Oriflamme": GoblinOriflamme,
            "Garruk's Uprising": GarruksUprising,
            "Authority of the Consuls": AuthorityOfTheConsuls,
            "Phyrexian Arena": PhyrexianArena,
            "Impact Tremors": ImpactTremors,
            "Rite of the Dragoncaller": RiteOfTheDragoncaller,
            "Painful Quandary": PainfulQuandary,
            "Banishing Light": BanishingLight,
            "Vampiric Rites": VampiricRites,
        }
        for name, cls in class_map.items():
            impl_class, metadata = registry.get(name)
            instance = impl_class()
            assert isinstance(instance, cls)
