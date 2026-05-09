"""Tests for cards/foundations/etb_creatures.py — Batch 5 ETB creatures.

All 29 creatures are from the MTG Foundations (FDN) set.

Verifies:
- Card metadata (name, mana cost, power/toughness, subtypes, keywords).
- ETB trigger registers correctly via register_triggers().
- ETB trigger fires on ENTERS_BATTLEFIELD event and effect resolves:
  draw, lifegain, tokens, damage, destroy/exile, bounce, counters,
  discard, debuff, graveyard return.
- register_etb_creatures() registers all cards in the registry.
"""

from __future__ import annotations

import pytest

from cards.foundations.etb_creatures import (
    AmbushWolf,
    AngelOfFinality,
    ArbiterOfWoe,
    BigfinBouncer,
    BurglarRat,
    BurrogBefuddler,
    Cloudblazer,
    DragonTrainer,
    ElvishRegrower,
    ExclusionMage,
    FelidarSavior,
    GuardedHeir,
    HelpfulHunter,
    IcewindElemental,
    InspiringOverseer,
    MassacreWurm,
    MeteorGolem,
    MischievousPup,
    PelakkaWurm,
    PridefulParent,
    RapaciousDragon,
    ReclamationSage,
    RegalCaracal,
    ResoluteReinforcements,
    ShipwreckDowser,
    SkeletonArcher,
    VampireSoulcaller,
    VampireSpawn,
    ViashinoPyromancer,
    register_etb_creatures,
)
from cards.registry import CardRegistry
from engine.card import ArtifactCreature, CardImpl, Creature, Enchantment, Instant
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.triggers import EventType
from engine.types import CardType, Keyword, ManaCost, Phase, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    """Create a minimal 2-player GameState."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _add_cards_to_library(player: DeterministicPlayer, n: int) -> list:
    """Add n dummy cards to a player's library and return them."""
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards


def _add_cards_to_hand(player: DeterministicPlayer, n: int) -> list:
    """Add n dummy cards to a player's hand and return them."""
    cards = []
    for i in range(n):
        c = CardImpl(name=f"HandCard{i}")
        c.owner = player
        player.zones[Zone.HAND].add(c)
        cards.append(c)
    return cards


def _simulate_etb(game: GameState, creature, controller=None):
    """Register triggers then fire ETB event, then resolve stack.

    This simulates the creature entering the battlefield:
    1. Register its triggers (so the ETB handler is listening).
    2. Fire ENTERS_BATTLEFIELD with the creature as the permanent.
    3. Resolve all stack objects pushed by the trigger.
    """
    if controller is None:
        controller = getattr(creature, "controller", game.players[0])
    creature.register_triggers(game)
    game.trigger_manager.fire_event(
        game,
        EventType.ENTERS_BATTLEFIELD,
        {"permanent": creature, "controller": controller},
    )
    # Resolve all triggered abilities on the stack
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)


def _place_on_battlefield(game: GameState, creature, player):
    """Place creature on a player's battlefield with ownership set."""
    creature.owner = player
    creature.controller = player
    game.get_battlefield(player).add(creature)


# ===================================================================
# DRAW — HelpfulHunter, InspiringOverseer, Cloudblazer, IcewindElemental
# ===================================================================


class TestHelpfulHunter:
    """Helpful Hunter — {1}{W} 1/1 Cat — ETB: draw a card."""

    def test_stats(self) -> None:
        c = HelpfulHunter()
        assert c.name == "Helpful Hunter"
        assert c.mana_cost == ManaCost.parse("{1}{W}")
        assert c.base_power == 1
        assert c.base_toughness == 1
        assert "Cat" in c.subtypes

    def test_etb_draws_one_card(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        hunter = HelpfulHunter(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_etb(game, hunter)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1


class TestInspiringOverseer:
    """Inspiring Overseer — {2}{W} 2/1 Angel Cleric Flying — ETB: gain 1 life, draw a card."""

    def test_stats_and_flying(self) -> None:
        c = InspiringOverseer()
        assert c.name == "Inspiring Overseer"
        assert c.mana_cost == ManaCost.parse("{2}{W}")
        assert c.base_power == 2
        assert c.base_toughness == 1
        assert Keyword.FLYING in c.keywords

    def test_etb_gains_life_and_draws(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        life_before = p1.life
        overseer = InspiringOverseer(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_etb(game, overseer)
        assert p1.life == life_before + 1
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 1


class TestCloudblazer:
    """Cloudblazer — {3}{W}{U} 2/2 Human Scout Flying — ETB: gain 2 life, draw 2."""

    def test_stats(self) -> None:
        c = Cloudblazer()
        assert c.name == "Cloudblazer"
        assert c.mana_cost == ManaCost.parse("{3}{W}{U}")
        assert c.base_power == 2
        assert c.base_toughness == 2
        assert Keyword.FLYING in c.keywords

    def test_etb_gains_2_life_draws_2(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        life_before = p1.life
        cb = Cloudblazer(owner=p1, controller=p1)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        _simulate_etb(game, cb)
        assert p1.life == life_before + 2
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before + 2


class TestIcewindElemental:
    """Icewind Elemental — {4}{U} 3/4 Elemental Flying — ETB: draw then discard."""

    def test_stats(self) -> None:
        c = IcewindElemental()
        assert c.name == "Icewind Elemental"
        assert c.base_power == 3
        assert c.base_toughness == 4
        assert Keyword.FLYING in c.keywords

    def test_etb_draws_then_discards(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 3)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        elem = IcewindElemental(owner=p1, controller=p1)
        _simulate_etb(game, elem)
        # Draw 1, discard 1 → net hand size unchanged
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before
        # A card should be in graveyard from the discard
        assert len(p1.zones[Zone.GRAVEYARD].get_all()) >= 1


# ===================================================================
# LIFEGAIN — PelakkaWurm, VampireSpawn
# ===================================================================


class TestPelakkaWurm:
    """Pelakka Wurm — {4}{G}{G}{G} 7/7 Wurm Trample — ETB: gain 7 life."""

    def test_stats(self) -> None:
        c = PelakkaWurm()
        assert c.name == "Pelakka Wurm"
        assert c.base_power == 7
        assert c.base_toughness == 7
        assert Keyword.TRAMPLE in c.keywords

    def test_etb_gains_7_life(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        life_before = p1.life
        wurm = PelakkaWurm(owner=p1, controller=p1)
        _simulate_etb(game, wurm)
        assert p1.life == life_before + 7


class TestVampireSpawn:
    """Vampire Spawn — {2}{B} 2/3 Vampire — ETB: opponents lose 2 life, you gain 2."""

    def test_stats(self) -> None:
        c = VampireSpawn()
        assert c.name == "Vampire Spawn"
        assert c.base_power == 2
        assert c.base_toughness == 3

    def test_etb_drains_opponents(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1_life = p1.life
        p2_life = p2.life
        spawn = VampireSpawn(owner=p1, controller=p1)
        _simulate_etb(game, spawn)
        assert p1.life == p1_life + 2
        assert p2.life == p2_life - 2


# ===================================================================
# TOKENS — PridefulParent, ResoluteReinforcements, GuardedHeir,
#           DragonTrainer, RegalCaracal, RapaciousDragon
# ===================================================================


class TestPridefulParent:
    """Prideful Parent — {2}{W} 2/2 Cat Vigilance — ETB: create 1/1 Cat token."""

    def test_stats(self) -> None:
        c = PridefulParent()
        assert c.name == "Prideful Parent"
        assert c.base_power == 2
        assert c.base_toughness == 2
        assert Keyword.VIGILANCE in c.keywords

    def test_etb_creates_cat_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        parent = PridefulParent(owner=p1, controller=p1)
        _simulate_etb(game, parent)
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) == 1
        assert tokens[0].name == "Cat"
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1


class TestResoluteReinforcements:
    """Resolute Reinforcements — {1}{W} 1/1 Human Soldier Flash — ETB: create 1/1 Soldier."""

    def test_has_flash(self) -> None:
        c = ResoluteReinforcements()
        assert Keyword.FLASH in c.keywords

    def test_etb_creates_soldier_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        rr = ResoluteReinforcements(owner=p1, controller=p1)
        _simulate_etb(game, rr)
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) == 1
        assert tokens[0].name == "Soldier"


class TestGuardedHeir:
    """Guarded Heir — {5}{W} 1/1 Human Noble Lifelink — ETB: two 3/3 Knight tokens."""

    def test_stats(self) -> None:
        c = GuardedHeir()
        assert c.base_power == 1
        assert c.base_toughness == 1
        assert Keyword.LIFELINK in c.keywords

    def test_etb_creates_two_knight_tokens(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        heir = GuardedHeir(owner=p1, controller=p1)
        _simulate_etb(game, heir)
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) == 2
        for t in tokens:
            assert t.name == "Knight"
            assert t.base_power == 3
            assert t.base_toughness == 3


class TestDragonTrainer:
    """Dragon Trainer — {3}{R}{R} 1/1 Human — ETB: 4/4 Dragon token with flying."""

    def test_etb_creates_dragon_token_with_flying(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        trainer = DragonTrainer(owner=p1, controller=p1)
        _simulate_etb(game, trainer)
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) == 1
        dragon = tokens[0]
        assert dragon.name == "Dragon"
        assert dragon.base_power == 4
        assert dragon.base_toughness == 4
        assert Keyword.FLYING in dragon.keywords


class TestRegalCaracal:
    """Regal Caracal — {3}{W}{W} 3/3 Cat — ETB: two 1/1 Cat tokens with lifelink."""

    def test_stats(self) -> None:
        c = RegalCaracal()
        assert c.name == "Regal Caracal"
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_etb_creates_two_cat_tokens(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        caracal = RegalCaracal(owner=p1, controller=p1)
        _simulate_etb(game, caracal)
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) == 2
        for t in tokens:
            assert t.name == "Cat"
            assert t.base_power == 1
            assert t.base_toughness == 1


class TestRapaciousDragon:
    """Rapacious Dragon — {4}{R} 3/3 Dragon Flying — ETB: two Treasure tokens."""

    def test_stats(self) -> None:
        c = RapaciousDragon()
        assert c.name == "Rapacious Dragon"
        assert Keyword.FLYING in c.keywords

    def test_etb_creates_two_treasure_tokens(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        dragon = RapaciousDragon(owner=p1, controller=p1)
        _simulate_etb(game, dragon)
        bf = game.get_battlefield(p1).get_all()
        tokens = [c for c in bf if getattr(c, "is_token", False)]
        assert len(tokens) == 2
        for t in tokens:
            assert t.name == "Treasure"


# ===================================================================
# DAMAGE — SkeletonArcher, ViashinoPyromancer
# ===================================================================


class TestSkeletonArcher:
    """Skeleton Archer — {3}{B} 3/3 — ETB: deals 1 damage to any target."""

    def test_stats(self) -> None:
        c = SkeletonArcher()
        assert c.name == "Skeleton Archer"
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_etb_deals_1_damage_to_player(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        archer = SkeletonArcher(owner=p1, controller=p1)
        archer.chosen_targets = [p2]
        life_before = p2.life
        _simulate_etb(game, archer)
        assert p2.life == life_before - 1

    def test_etb_deals_1_damage_to_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        _place_on_battlefield(game, target, p2)
        archer = SkeletonArcher(owner=p1, controller=p1)
        archer.chosen_targets = [target]
        _simulate_etb(game, archer)
        # 1 damage marked on the creature
        assert getattr(target, "damage_marked", 0) == 1


class TestViashinoPyromancer:
    """Viashino Pyromancer — {1}{R} 2/1 — ETB: deals 2 damage to target player."""

    def test_stats(self) -> None:
        c = ViashinoPyromancer()
        assert c.name == "Viashino Pyromancer"
        assert c.base_power == 2
        assert c.base_toughness == 1

    def test_etb_deals_2_damage_to_player(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        pyro = ViashinoPyromancer(owner=p1, controller=p1)
        pyro.chosen_targets = [p2]
        life_before = p2.life
        _simulate_etb(game, pyro)
        assert p2.life == life_before - 2


# ===================================================================
# DESTROY / EXILE — ReclamationSage, MeteorGolem, AmbushWolf, AngelOfFinality
# ===================================================================


class TestReclamationSage:
    """Reclamation Sage — {2}{G} 2/1 — ETB: may destroy target artifact or enchantment."""

    def test_stats(self) -> None:
        c = ReclamationSage()
        assert c.name == "Reclamation Sage"
        assert c.base_power == 2
        assert c.base_toughness == 1

    def test_etb_destroys_enchantment(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        enchant = Enchantment(name="Bad Enchantment", owner=p2, controller=p2)
        _place_on_battlefield(game, enchant, p2)
        sage = ReclamationSage(owner=p1, controller=p1)
        sage.chosen_targets = [enchant]
        _simulate_etb(game, sage)
        bf = game.get_battlefield(p2).get_all()
        assert enchant not in bf

    def test_etb_does_not_destroy_creature(self) -> None:
        """ReclamationSage should only destroy artifacts/enchantments."""
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        bear = Creature(name="Bear", base_power=2, base_toughness=2,
                        owner=p2, controller=p2)
        _place_on_battlefield(game, bear, p2)
        sage = ReclamationSage(owner=p1, controller=p1)
        sage.chosen_targets = [bear]
        _simulate_etb(game, sage)
        bf = game.get_battlefield(p2).get_all()
        assert bear in bf  # should NOT be destroyed


class TestMeteorGolem:
    """Meteor Golem — {7} 3/3 Artifact Creature Golem — ETB: destroy target nonland permanent."""

    def test_is_artifact_creature(self) -> None:
        c = MeteorGolem()
        assert isinstance(c, ArtifactCreature)
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_etb_destroys_target_permanent(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Big Creature", base_power=5, base_toughness=5,
                          owner=p2, controller=p2)
        _place_on_battlefield(game, target, p2)
        golem = MeteorGolem(owner=p1, controller=p1)
        golem.chosen_targets = [target]
        _simulate_etb(game, golem)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf


class TestAmbushWolf:
    """Ambush Wolf — {2}{G} 4/2 Wolf Flash — ETB: exile target card from graveyard."""

    def test_stats(self) -> None:
        c = AmbushWolf()
        assert c.name == "Ambush Wolf"
        assert c.base_power == 4
        assert c.base_toughness == 2
        assert Keyword.FLASH in c.keywords

    def test_etb_exiles_card_from_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        gy_card = CardImpl(name="Dead Card")
        gy_card.owner = p2
        p2.zones[Zone.GRAVEYARD].add(gy_card)
        wolf = AmbushWolf(owner=p1, controller=p1)
        wolf.chosen_targets = [gy_card]
        _simulate_etb(game, wolf)
        assert not p2.zones[Zone.GRAVEYARD].contains(gy_card)
        assert p2.zones[Zone.EXILE].contains(gy_card)


class TestAngelOfFinality:
    """Angel of Finality — {3}{W} 3/4 Angel Flying — ETB: exile target player's graveyard."""

    def test_stats(self) -> None:
        c = AngelOfFinality()
        assert c.name == "Angel of Finality"
        assert c.base_power == 3
        assert c.base_toughness == 4
        assert Keyword.FLYING in c.keywords

    def test_etb_exiles_opponents_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        gy_cards = []
        for i in range(3):
            c = CardImpl(name=f"GYCard{i}")
            c.owner = p2
            p2.zones[Zone.GRAVEYARD].add(c)
            gy_cards.append(c)
        angel = AngelOfFinality(owner=p1, controller=p1)
        angel.chosen_targets = [p2]
        _simulate_etb(game, angel)
        assert len(p2.zones[Zone.GRAVEYARD].get_all()) == 0
        assert len(p2.zones[Zone.EXILE].get_all()) == 3


# ===================================================================
# BOUNCE — BigfinBouncer, ExclusionMage, MischievousPup
# ===================================================================


class TestBigfinBouncer:
    """Bigfin Bouncer — {3}{U} 3/2 — ETB: return target opponent creature to hand."""

    def test_stats(self) -> None:
        c = BigfinBouncer()
        assert c.name == "Bigfin Bouncer"
        assert c.base_power == 3
        assert c.base_toughness == 2

    def test_etb_bounces_opponent_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Enemy Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        _place_on_battlefield(game, target, p2)
        bouncer = BigfinBouncer(owner=p1, controller=p1)
        bouncer.chosen_targets = [target]
        _simulate_etb(game, bouncer)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf
        assert p2.zones[Zone.HAND].contains(target)


class TestExclusionMage:
    """Exclusion Mage — {2}{U} 2/2 — ETB: return target opponent creature to hand."""

    def test_stats(self) -> None:
        c = ExclusionMage()
        assert c.name == "Exclusion Mage"
        assert c.base_power == 2
        assert c.base_toughness == 2

    def test_etb_bounces_opponent_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Enemy Bear", base_power=2, base_toughness=2,
                          owner=p2, controller=p2)
        _place_on_battlefield(game, target, p2)
        mage = ExclusionMage(owner=p1, controller=p1)
        mage.chosen_targets = [target]
        _simulate_etb(game, mage)
        bf = game.get_battlefield(p2).get_all()
        assert target not in bf
        assert p2.zones[Zone.HAND].contains(target)


class TestMischievousPup:
    """Mischievous Pup — {2}{W} 3/1 Dog — ETB: return own permanent to hand."""

    def test_stats(self) -> None:
        c = MischievousPup()
        assert c.name == "Mischievous Pup"
        assert c.base_power == 3
        assert c.base_toughness == 1

    def test_etb_bounces_own_permanent(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        target = Creature(name="My Bear", base_power=2, base_toughness=2,
                          owner=p1, controller=p1)
        _place_on_battlefield(game, target, p1)
        pup = MischievousPup(owner=p1, controller=p1)
        pup.chosen_targets = [target]
        _simulate_etb(game, pup)
        bf = game.get_battlefield(p1).get_all()
        assert target not in bf
        assert p1.zones[Zone.HAND].contains(target)


# ===================================================================
# GRAVEYARD RETURN — VampireSoulcaller, ElvishRegrower, ShipwreckDowser
# ===================================================================


class TestVampireSoulcaller:
    """Vampire Soulcaller — {4}{B} 3/2 Vampire Flying — ETB: return creature from GY to hand."""

    def test_stats(self) -> None:
        c = VampireSoulcaller()
        assert c.name == "Vampire Soulcaller"
        assert c.base_power == 3
        assert c.base_toughness == 2
        assert Keyword.FLYING in c.keywords

    def test_etb_returns_creature_from_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        dead_creature = Creature(name="Dead Bear", base_power=2, base_toughness=2,
                                 owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(dead_creature)
        soulcaller = VampireSoulcaller(owner=p1, controller=p1)
        soulcaller.chosen_targets = [dead_creature]
        _simulate_etb(game, soulcaller)
        assert not p1.zones[Zone.GRAVEYARD].contains(dead_creature)
        assert p1.zones[Zone.HAND].contains(dead_creature)


class TestElvishRegrower:
    """Elvish Regrower — {2}{G}{G} 4/3 — ETB: return permanent card from GY to hand."""

    def test_stats(self) -> None:
        c = ElvishRegrower()
        assert c.name == "Elvish Regrower"
        assert c.base_power == 4
        assert c.base_toughness == 3

    def test_etb_returns_permanent_from_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        dead_enchant = Enchantment(name="Lost Enchantment", owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(dead_enchant)
        regrower = ElvishRegrower(owner=p1, controller=p1)
        regrower.chosen_targets = [dead_enchant]
        _simulate_etb(game, regrower)
        assert not p1.zones[Zone.GRAVEYARD].contains(dead_enchant)
        assert p1.zones[Zone.HAND].contains(dead_enchant)


class TestShipwreckDowser:
    """Shipwreck Dowser — {3}{U}{U} 3/3 Prowess — ETB: return instant/sorcery from GY to hand."""

    def test_stats(self) -> None:
        c = ShipwreckDowser()
        assert c.name == "Shipwreck Dowser"
        assert c.base_power == 3
        assert c.base_toughness == 3

    def test_etb_returns_instant_from_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        dead_spell = Instant(name="Lightning Bolt", owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(dead_spell)
        dowser = ShipwreckDowser(owner=p1, controller=p1)
        dowser.chosen_targets = [dead_spell]
        _simulate_etb(game, dowser)
        assert not p1.zones[Zone.GRAVEYARD].contains(dead_spell)
        assert p1.zones[Zone.HAND].contains(dead_spell)

    def test_etb_does_not_return_creature_from_graveyard(self) -> None:
        """Should only return instants/sorceries, not creatures."""
        game = _make_game()
        p1 = game.players[0]
        dead_creature = Creature(name="Dead Bear", base_power=2, base_toughness=2,
                                 owner=p1, controller=p1)
        p1.zones[Zone.GRAVEYARD].add(dead_creature)
        dowser = ShipwreckDowser(owner=p1, controller=p1)
        dowser.chosen_targets = [dead_creature]
        _simulate_etb(game, dowser)
        # Should still be in graveyard, not returned
        assert p1.zones[Zone.GRAVEYARD].contains(dead_creature)
        assert not p1.zones[Zone.HAND].contains(dead_creature)


# ===================================================================
# COUNTERS — FelidarSavior
# ===================================================================


class TestFelidarSavior:
    """Felidar Savior — {3}{W} 2/3 Cat Beast Lifelink — ETB: +1/+1 counters on targets."""

    def test_stats(self) -> None:
        c = FelidarSavior()
        assert c.name == "Felidar Savior"
        assert c.base_power == 2
        assert c.base_toughness == 3
        assert Keyword.LIFELINK in c.keywords

    def test_etb_adds_counters_to_two_targets(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        t1 = Creature(name="Bear1", base_power=2, base_toughness=2,
                       owner=p1, controller=p1)
        t2 = Creature(name="Bear2", base_power=3, base_toughness=3,
                       owner=p1, controller=p1)
        _place_on_battlefield(game, t1, p1)
        _place_on_battlefield(game, t2, p1)
        savior = FelidarSavior(owner=p1, controller=p1)
        savior.chosen_targets = [t1, t2]
        _simulate_etb(game, savior)
        assert getattr(t1, "plus_one_counters", 0) == 1
        assert getattr(t2, "plus_one_counters", 0) == 1

    def test_etb_does_not_counter_self(self) -> None:
        """Felidar Savior should not put counters on itself (other targets only)."""
        game = _make_game()
        p1 = game.players[0]
        savior = FelidarSavior(owner=p1, controller=p1)
        _place_on_battlefield(game, savior, p1)
        savior.chosen_targets = [savior]
        _simulate_etb(game, savior)
        assert getattr(savior, "plus_one_counters", 0) == 0


# ===================================================================
# DISCARD — BurglarRat, ArbiterOfWoe
# ===================================================================


class TestBurglarRat:
    """Burglar Rat — {1}{B} 1/1 Rat — ETB: each opponent discards a card."""

    def test_stats(self) -> None:
        c = BurglarRat()
        assert c.name == "Burglar Rat"
        assert c.base_power == 1
        assert c.base_toughness == 1

    def test_etb_forces_opponent_discard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _add_cards_to_hand(p2, 3)
        hand_before = len(p2.zones[Zone.HAND].get_all())
        rat = BurglarRat(owner=p1, controller=p1)
        _simulate_etb(game, rat)
        assert len(p2.zones[Zone.HAND].get_all()) == hand_before - 1

    def test_etb_does_not_discard_controller(self) -> None:
        """Controller should not be forced to discard."""
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_hand(p1, 3)
        hand_before = len(p1.zones[Zone.HAND].get_all())
        rat = BurglarRat(owner=p1, controller=p1)
        _simulate_etb(game, rat)
        assert len(p1.zones[Zone.HAND].get_all()) == hand_before


class TestArbiterOfWoe:
    """Arbiter of Woe — {4}{B}{B} 5/4 Demon Flying — ETB: opponent discards, loses 2; you draw, gain 2."""

    def test_stats(self) -> None:
        c = ArbiterOfWoe()
        assert c.name == "Arbiter of Woe"
        assert c.base_power == 5
        assert c.base_toughness == 4
        assert Keyword.FLYING in c.keywords

    def test_etb_drains_opponent_and_benefits_controller(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _add_cards_to_hand(p2, 3)
        _add_cards_to_library(p1, 3)
        p1_life = p1.life
        p2_life = p2.life
        p2_hand = len(p2.zones[Zone.HAND].get_all())
        p1_hand = len(p1.zones[Zone.HAND].get_all())
        arbiter = ArbiterOfWoe(owner=p1, controller=p1)
        _simulate_etb(game, arbiter)
        # Opponent discards 1 and loses 2 life
        assert len(p2.zones[Zone.HAND].get_all()) == p2_hand - 1
        assert p2.life == p2_life - 2
        # Controller draws 1 and gains 2 life
        assert len(p1.zones[Zone.HAND].get_all()) == p1_hand + 1
        assert p1.life == p1_life + 2


# ===================================================================
# DEBUFF — BurrogBefuddler, MassacreWurm
# ===================================================================


class TestBurrogBefuddler:
    """Burrog Befuddler — {1}{U} 2/1 Frog Wizard Flash — ETB: target gets -1/-0 EOT."""

    def test_stats(self) -> None:
        c = BurrogBefuddler()
        assert c.name == "Burrog Befuddler"
        assert c.base_power == 2
        assert c.base_toughness == 1
        assert Keyword.FLASH in c.keywords

    def test_etb_debuffs_target_creature(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        target = Creature(name="Enemy Bear", base_power=3, base_toughness=3,
                          owner=p2, controller=p2)
        _place_on_battlefield(game, target, p2)
        power_before = target.base_power
        frog = BurrogBefuddler(owner=p1, controller=p1)
        frog.chosen_targets = [target]
        _simulate_etb(game, frog)
        # Apply effects
        game.effect_manager.apply_all(game)
        assert target.base_power == power_before - 1


class TestMassacreWurm:
    """Massacre Wurm — {3}{B}{B}{B} 6/5 — ETB: opponents' creatures get -2/-2 EOT."""

    def test_stats(self) -> None:
        c = MassacreWurm()
        assert c.name == "Massacre Wurm"
        assert c.base_power == 6
        assert c.base_toughness == 5

    def test_etb_debuffs_all_opponent_creatures(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        c1 = Creature(name="Bear1", base_power=3, base_toughness=3,
                       owner=p2, controller=p2)
        c2 = Creature(name="Bear2", base_power=4, base_toughness=4,
                       owner=p2, controller=p2)
        _place_on_battlefield(game, c1, p2)
        _place_on_battlefield(game, c2, p2)
        wurm = MassacreWurm(owner=p1, controller=p1)
        _simulate_etb(game, wurm)
        game.effect_manager.apply_all(game)
        assert c1.base_power == 1  # 3 - 2
        assert c1.base_toughness == 1  # 3 - 2
        assert c2.base_power == 2  # 4 - 2
        assert c2.base_toughness == 2  # 4 - 2

    def test_etb_does_not_debuff_own_creatures(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        own = Creature(name="Own Bear", base_power=3, base_toughness=3,
                        owner=p1, controller=p1)
        _place_on_battlefield(game, own, p1)
        wurm = MassacreWurm(owner=p1, controller=p1)
        _simulate_etb(game, wurm)
        game.effect_manager.apply_all(game)
        assert own.base_power == 3  # unchanged
        assert own.base_toughness == 3


# ===================================================================
# TRIGGER REGISTRATION — verify register_triggers adds a trigger
# ===================================================================


class TestTriggerRegistration:
    """Each ETB creature should register at least one trigger."""

    @pytest.mark.parametrize("cls", [
        HelpfulHunter, InspiringOverseer, Cloudblazer, IcewindElemental,
        PelakkaWurm, VampireSpawn,
        PridefulParent, ResoluteReinforcements, GuardedHeir, DragonTrainer,
        RegalCaracal, RapaciousDragon,
        SkeletonArcher, ViashinoPyromancer,
        ReclamationSage, MeteorGolem, AmbushWolf,
        BigfinBouncer, ExclusionMage, VampireSoulcaller, MischievousPup,
        FelidarSavior,
        BurglarRat, ArbiterOfWoe,
        BurrogBefuddler, MassacreWurm,
        ElvishRegrower, AngelOfFinality, ShipwreckDowser,
    ])
    def test_registers_etb_trigger(self, cls) -> None:
        game = _make_game()
        p1 = game.players[0]
        creature = cls(owner=p1, controller=p1)
        creature.register_triggers(game)
        triggers = game.trigger_manager.get_triggers_for_source(creature)
        assert len(triggers) >= 1
        # At least one should be an ETB trigger
        etb_triggers = [t for t in triggers if t.event_type == EventType.ENTERS_BATTLEFIELD]
        assert len(etb_triggers) >= 1


# ===================================================================
# REGISTRY — register_etb_creatures
# ===================================================================


class TestRegistry:
    """register_etb_creatures should register all 29 creatures."""

    EXPECTED_NAMES = [
        "Helpful Hunter", "Inspiring Overseer", "Cloudblazer", "Icewind Elemental",
        "Pelakka Wurm", "Vampire Spawn",
        "Prideful Parent", "Resolute Reinforcements", "Guarded Heir",
        "Dragon Trainer", "Regal Caracal", "Rapacious Dragon",
        "Skeleton Archer", "Viashino Pyromancer",
        "Reclamation Sage", "Meteor Golem",
        "Ambush Wolf", "Bigfin Bouncer", "Exclusion Mage",
        "Vampire Soulcaller", "Mischievous Pup",
        "Felidar Savior",
        "Burglar Rat", "Arbiter of Woe",
        "Burrog Befuddler", "Massacre Wurm",
        "Elvish Regrower", "Angel of Finality", "Shipwreck Dowser",
    ]

    def test_all_cards_registered(self) -> None:
        registry = CardRegistry()
        register_etb_creatures(registry)
        for name in self.EXPECTED_NAMES:
            assert registry.get(name) is not None, f"{name} not found in registry"

    def test_registry_count(self) -> None:
        registry = CardRegistry()
        register_etb_creatures(registry)
        # Should have at least 29 cards
        registered_count = sum(1 for name in self.EXPECTED_NAMES if registry.get(name) is not None)
        assert registered_count == 29

    def test_registry_metadata_set_code(self) -> None:
        """All registered cards should have set_code='fdn'."""
        registry = CardRegistry()
        register_etb_creatures(registry)
        for name in self.EXPECTED_NAMES:
            entry = registry.get(name)
            if entry is not None:
                metadata = entry.metadata if hasattr(entry, "metadata") else entry
                if hasattr(metadata, "set_code"):
                    assert metadata.set_code == "fdn", f"{name} has wrong set_code"
