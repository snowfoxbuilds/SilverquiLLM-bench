"""Tests for cards/foundations/simple_spells_batch2.py — Batch 2 non-targeted spells.

All 15 spells are from the MTG Foundations (FDN) set with Scryfall-verified data.

Verifies:
- Each spell has the correct name, mana_cost, card types (Instant vs Sorcery).
- Draw spells: correct number of cards drawn.
- Lifegain spells: life total changes.
- Token creation spells: correct tokens on battlefield.
- Each player/opponent effects: effects applied to all/opponent players.
- register_simple_spells_batch2() registers all 15 in the registry.
- Registry metadata accuracy (oracle_text, rarity, type_line, set_code).
"""

from __future__ import annotations

import pytest

from cards.foundations.simple_spells_batch2 import (
    AntiquitiesOnTheLoose,
    EmbraceTheParadox,
    FractalAnomaly,
    GroupProject,
    MusesEncouragement,
    PoxPlague,
    PursueThePast,
    RapturousMoment,
    SeizeTheSpoils,
    SendInThePest,
    SnarlSong,
    SocialSnub,
    VisionarysDance,
    WisdomOfAges,
    WitheringCurse,
    register_simple_spells_batch2,
)
from cards.registry import CardRegistry
from engine.card import Creature, Instant, Sorcery
from engine.game_state import GameState
from engine.player import DeterministicPlayer
from engine.types import CardType, Keyword, ManaCost, Phase, Zone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_game(
    *,
    phase: Phase = Phase.PRECOMBAT_MAIN,
) -> GameState:
    """Create a minimal 2-player GameState at the specified phase."""
    p1 = DeterministicPlayer("Alice", [])
    p2 = DeterministicPlayer("Bob", [])
    game = GameState([p1, p2])
    game.phase = phase
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0
    return game


def _make_creature(
    name: str = "Test Creature",
    power: int = 2,
    toughness: int = 3,
    owner: DeterministicPlayer | None = None,
    controller: DeterministicPlayer | None = None,
) -> Creature:
    """Create a minimal creature for testing."""
    return Creature(
        name=name,
        base_power=power,
        base_toughness=toughness,
        owner=owner,
        controller=controller,
    )


def _add_cards_to_library(player: DeterministicPlayer, n: int) -> list:
    """Add n dummy cards to a player's library and return them."""
    from engine.card import CardImpl
    cards = []
    for i in range(n):
        c = CardImpl(name=f"LibCard{i}")
        c.owner = player
        player.zones[Zone.LIBRARY].add(c)
        cards.append(c)
    return cards


def _add_cards_to_hand(player: DeterministicPlayer, n: int) -> list:
    """Add n dummy cards to a player's hand and return them."""
    from engine.card import CardImpl
    cards = []
    for i in range(n):
        c = CardImpl(name=f"HandCard{i}")
        c.owner = player
        player.zones[Zone.HAND].add(c)
        cards.append(c)
    return cards


# ---------------------------------------------------------------------------
# Draw spells
# ---------------------------------------------------------------------------


class TestEmbraceTheParadox:
    """Embrace the Paradox — {3}{G}{U} — Draw three cards."""

    def test_is_instant(self) -> None:
        spell = EmbraceTheParadox()
        assert isinstance(spell, Instant)

    def test_name_and_cost(self) -> None:
        spell = EmbraceTheParadox()
        assert spell.name == "Embrace the Paradox"
        assert spell.mana_cost == ManaCost.parse("{3}{G}{U}")

    def test_draws_three_cards(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        spell = EmbraceTheParadox(owner=p1, controller=p1)

        hand_before = len(game.get_hand(p1))
        spell.on_resolve(game)
        hand_after = len(game.get_hand(p1))
        assert hand_after - hand_before == 3

    def test_no_targets(self) -> None:
        game = _make_game()
        spell = EmbraceTheParadox()
        assert spell.get_targets(game) == []


class TestRapturousMoment:
    """Rapturous Moment — {4}{U}{R} — Draw 3, discard 2."""

    def test_is_sorcery(self) -> None:
        spell = RapturousMoment()
        assert isinstance(spell, Sorcery)

    def test_name_and_cost(self) -> None:
        spell = RapturousMoment()
        assert spell.name == "Rapturous Moment"
        assert spell.mana_cost == ManaCost.parse("{4}{U}{R}")

    def test_draws_three_then_discards_two(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        spell = RapturousMoment(owner=p1, controller=p1)

        hand_before = len(game.get_hand(p1))
        spell.on_resolve(game)
        hand_after = len(game.get_hand(p1))
        # Net: draw 3 - discard 2 = +1
        assert hand_after - hand_before == 1

    def test_graveyard_gets_discards(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        spell = RapturousMoment(owner=p1, controller=p1)

        gy_before = len(game.get_graveyard(p1))
        spell.on_resolve(game)
        gy_after = len(game.get_graveyard(p1))
        assert gy_after - gy_before == 2


class TestWisdomOfAges:
    """Wisdom of Ages — {4}{U}{U}{U} — Return instants/sorceries from GY."""

    def test_is_sorcery(self) -> None:
        spell = WisdomOfAges()
        assert isinstance(spell, Sorcery)

    def test_returns_instants_sorceries_from_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]

        # Put an instant and a sorcery in graveyard
        inst = Instant(name="Test Instant")
        sorc = Sorcery(name="Test Sorcery")
        creature = Creature(name="Test Creature", base_power=1, base_toughness=1)
        p1.zones[Zone.GRAVEYARD].add(inst)
        p1.zones[Zone.GRAVEYARD].add(sorc)
        p1.zones[Zone.GRAVEYARD].add(creature)

        spell = WisdomOfAges(owner=p1, controller=p1)
        spell.on_resolve(game)

        hand = game.get_hand(p1)
        gy = game.get_graveyard(p1)

        # Instant and sorcery should be in hand
        assert hand.contains(inst)
        assert hand.contains(sorc)
        # Creature stays in graveyard
        assert gy.contains(creature)
        assert not gy.contains(inst)
        assert not gy.contains(sorc)


# ---------------------------------------------------------------------------
# Lifegain + draw spells
# ---------------------------------------------------------------------------


class TestPursueThePast:
    """Pursue the Past — {R}{W} — Gain 2 life, may discard to draw 2."""

    def test_is_sorcery(self) -> None:
        spell = PursueThePast()
        assert isinstance(spell, Sorcery)

    def test_gains_two_life(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        _add_cards_to_hand(p1, 1)
        _add_cards_to_library(p1, 5)
        spell = PursueThePast(owner=p1, controller=p1)

        spell.on_resolve(game)
        assert p1.life == 22

    def test_discards_and_draws_when_has_cards(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        hand_cards = _add_cards_to_hand(p1, 2)
        _add_cards_to_library(p1, 5)
        spell = PursueThePast(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Started with 2, discarded 1, drew 2 => net 3
        hand = game.get_hand(p1)
        assert len(hand) == 3

    def test_no_discard_if_empty_hand(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        spell = PursueThePast(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Still gains life
        assert p1.life == 22
        # No cards drawn (hand was empty, nothing to discard)
        assert len(game.get_hand(p1)) == 0


class TestSeizeTheSpoils:
    """Seize the Spoils — {2}{R} — Draw 2 + create Treasure token."""

    def test_is_sorcery(self) -> None:
        spell = SeizeTheSpoils()
        assert isinstance(spell, Sorcery)

    def test_draws_two_cards(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        spell = SeizeTheSpoils(owner=p1, controller=p1)

        spell.on_resolve(game)
        assert len(game.get_hand(p1)) == 2

    def test_creates_treasure_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        spell = SeizeTheSpoils(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Treasure"
        ]
        assert len(tokens) == 1
        assert getattr(tokens[0], "is_token", False)


# ---------------------------------------------------------------------------
# Token creation spells
# ---------------------------------------------------------------------------


class TestGroupProject:
    """Group Project — {1}{W} — Create 2/2 Spirit token."""

    def test_is_sorcery(self) -> None:
        spell = GroupProject()
        assert isinstance(spell, Sorcery)

    def test_creates_spirit_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spell = GroupProject(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Spirit"
        ]
        assert len(tokens) == 1
        assert tokens[0].base_power == 2
        assert tokens[0].base_toughness == 2
        assert getattr(tokens[0], "is_token", False)


class TestMusesEncouragement:
    """Muse's Encouragement — {4}{U} — Create 3/3 Elemental with flying + Surveil 2."""

    def test_is_instant(self) -> None:
        spell = MusesEncouragement()
        assert isinstance(spell, Instant)

    def test_creates_elemental_token_with_flying(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        spell = MusesEncouragement(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Elemental"
        ]
        assert len(tokens) == 1
        assert tokens[0].base_power == 3
        assert tokens[0].base_toughness == 3
        assert Keyword.FLYING in (tokens[0].keywords or Keyword(0))

    def test_surveil_puts_cards_in_graveyard(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        _add_cards_to_library(p1, 5)
        spell = MusesEncouragement(owner=p1, controller=p1)

        gy_before = len(game.get_graveyard(p1))
        spell.on_resolve(game)
        gy_after = len(game.get_graveyard(p1))
        assert gy_after - gy_before == 2


class TestVisionarysDance:
    """Visionary's Dance — {5}{U}{R} — Create two 3/3 Elemental tokens with flying."""

    def test_is_sorcery(self) -> None:
        spell = VisionarysDance()
        assert isinstance(spell, Sorcery)

    def test_creates_two_elemental_tokens(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spell = VisionarysDance(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Elemental"
        ]
        assert len(tokens) == 2
        for t in tokens:
            assert t.base_power == 3
            assert t.base_toughness == 3
            assert Keyword.FLYING in (t.keywords or Keyword(0))


class TestAntiquitiesOnTheLoose:
    """Antiquities on the Loose — {1}{W}{W} — Create two 2/2 Spirit tokens."""

    def test_is_sorcery(self) -> None:
        spell = AntiquitiesOnTheLoose()
        assert isinstance(spell, Sorcery)

    def test_creates_two_spirit_tokens(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spell = AntiquitiesOnTheLoose(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Spirit"
        ]
        assert len(tokens) == 2
        for t in tokens:
            assert t.base_power == 2
            assert t.base_toughness == 2


class TestFractalAnomaly:
    """Fractal Anomaly — {U} — Create a 0/0 Fractal token with counters."""

    def test_is_instant(self) -> None:
        spell = FractalAnomaly()
        assert isinstance(spell, Instant)

    def test_creates_fractal_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spell = FractalAnomaly(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Fractal"
        ]
        assert len(tokens) == 1
        assert tokens[0].base_power == 0
        assert tokens[0].base_toughness == 0

    def test_counters_based_on_draws(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p1.cards_drawn_this_turn = 3
        spell = FractalAnomaly(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Fractal"
        ]
        assert tokens[0].plus_one_counters == 3


class TestSnarlSong:
    """Snarl Song — {5}{G} — Create two Fractal tokens + gain life."""

    def test_is_sorcery(self) -> None:
        spell = SnarlSong()
        assert isinstance(spell, Sorcery)

    def test_creates_two_fractal_tokens(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        spell = SnarlSong(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Fractal"
        ]
        assert len(tokens) == 2

    def test_gains_life(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        spell = SnarlSong(owner=p1, controller=p1)

        spell.on_resolve(game)
        # Default 1 color spent
        assert p1.life == 21


# ---------------------------------------------------------------------------
# Each player / opponent effects
# ---------------------------------------------------------------------------


class TestSendInThePest:
    """Send in the Pest — {1}{B} — Each opponent discards + create Pest token."""

    def test_is_sorcery(self) -> None:
        spell = SendInThePest()
        assert isinstance(spell, Sorcery)

    def test_opponent_discards(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        _add_cards_to_hand(p2, 3)
        spell = SendInThePest(owner=p1, controller=p1)

        spell.on_resolve(game)
        assert len(game.get_hand(p2)) == 2

    def test_creates_pest_token(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        spell = SendInThePest(owner=p1, controller=p1)

        spell.on_resolve(game)
        bf = game.get_battlefield(p1)
        tokens = [
            obj for obj in bf.get_all()
            if getattr(obj, "name", "") == "Pest"
        ]
        assert len(tokens) == 1
        assert tokens[0].base_power == 1
        assert tokens[0].base_toughness == 1


class TestWitheringCurse:
    """Withering Curse — {1}{B}{B} — All creatures get -2/-2 until end of turn."""

    def test_is_sorcery(self) -> None:
        spell = WitheringCurse()
        assert isinstance(spell, Sorcery)

    def test_registers_continuous_effect(self) -> None:
        game = _make_game()
        p1 = game.players[0]

        creature = _make_creature(power=4, toughness=4, owner=p1, controller=p1)
        game.get_battlefield(p1).add(creature)

        spell = WitheringCurse(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Apply continuous effects
        game.effect_manager.apply_all(game)

        assert creature.base_power == 2  # 4 - 2
        assert creature.base_toughness == 2  # 4 - 2


class TestSocialSnub:
    """Social Snub — {1}{W}{B} — Each player sacs creature, opponents lose 1 life."""

    def test_is_sorcery(self) -> None:
        spell = SocialSnub()
        assert isinstance(spell, Sorcery)

    def test_opponent_loses_life_controller_gains(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 20
        p2.life = 20

        spell = SocialSnub(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert p2.life == 19
        assert p1.life == 21

    def test_sacrifices_creatures(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 20
        p2.life = 20

        c1 = _make_creature(name="C1", owner=p1, controller=p1)
        c2 = _make_creature(name="C2", owner=p2, controller=p2)
        game.get_battlefield(p1).add(c1)
        game.get_battlefield(p2).add(c2)

        spell = SocialSnub(owner=p1, controller=p1)
        spell.on_resolve(game)

        # Both creatures should be gone (sacrificed)
        assert not game.get_battlefield(p1).contains(c1)
        assert not game.get_battlefield(p2).contains(c2)


class TestPoxPlague:
    """Pox Plague — {B}{B}{B}{B}{B} — Each player loses half life, discards half hand, sacs half permanents."""

    def test_is_sorcery(self) -> None:
        spell = PoxPlague()
        assert isinstance(spell, Sorcery)

    def test_loses_half_life(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 20
        p2.life = 20

        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert p1.life == 10
        assert p2.life == 10

    def test_discards_half_hand(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p2 = game.players[1]
        p1.life = 20
        p2.life = 20
        _add_cards_to_hand(p1, 4)
        _add_cards_to_hand(p2, 3)

        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert len(game.get_hand(p1)) == 2  # 4 -> discard 2
        assert len(game.get_hand(p2)) == 2  # 3 -> discard 1

    def test_sacrifices_half_permanents(self) -> None:
        game = _make_game()
        p1 = game.players[0]
        p1.life = 20
        game.players[1].life = 20

        c1 = _make_creature(name="C1", owner=p1, controller=p1)
        c2 = _make_creature(name="C2", owner=p1, controller=p1)
        c3 = _make_creature(name="C3", owner=p1, controller=p1)
        c4 = _make_creature(name="C4", owner=p1, controller=p1)
        for c in [c1, c2, c3, c4]:
            game.get_battlefield(p1).add(c)

        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)

        bf = game.get_battlefield(p1)
        assert len(list(bf.get_all())) == 2  # 4 -> sac 2


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

_EXPECTED_NAMES = {
    "Embrace the Paradox",
    "Rapturous Moment",
    "Wisdom of Ages",
    "Pursue the Past",
    "Seize the Spoils",
    "Group Project",
    "Muse's Encouragement",
    "Visionary's Dance",
    "Antiquities on the Loose",
    "Fractal Anomaly",
    "Snarl Song",
    "Send in the Pest",
    "Withering Curse",
    "Social Snub",
    "Pox Plague",
}


class TestRegisterSimpleSpellsBatch2:
    """Verify register_simple_spells_batch2 registers all 15 spells."""

    def test_registers_all_fifteen(self) -> None:
        registry = CardRegistry()
        register_simple_spells_batch2(registry)
        assert len(registry) == 15

    def test_registered_names(self) -> None:
        registry = CardRegistry()
        register_simple_spells_batch2(registry)
        assert set(registry.list_all()) == _EXPECTED_NAMES

    def test_create_instance_produces_correct_type(self) -> None:
        registry = CardRegistry()
        register_simple_spells_batch2(registry)
        player = DeterministicPlayer("TestPlayer", [])

        inst = registry.create_instance("Embrace the Paradox", owner=player)
        assert isinstance(inst, EmbraceTheParadox)
        assert isinstance(inst, Instant)

        sorc = registry.create_instance("Group Project", owner=player)
        assert isinstance(sorc, GroupProject)
        assert isinstance(sorc, Sorcery)


# ---------------------------------------------------------------------------
# Registry metadata accuracy
# ---------------------------------------------------------------------------

_EXPECTED_METADATA = [
    # (name, type_line, rarity, oracle_text_substr)
    ("Embrace the Paradox", "Instant", "common", "Draw three"),
    ("Rapturous Moment", "Sorcery", "uncommon", "Draw three cards"),
    ("Wisdom of Ages", "Sorcery", "rare", "instant and sorcery"),
    ("Pursue the Past", "Sorcery", "common", "gain 2 life"),
    ("Seize the Spoils", "Sorcery", "common", "Draw two cards"),
    ("Group Project", "Sorcery", "uncommon", "Spirit creature token"),
    ("Muse's Encouragement", "Instant", "common", "Elemental creature token"),
    ("Visionary's Dance", "Sorcery", "common", "Elemental creature tokens"),
    ("Antiquities on the Loose", "Sorcery", "rare", "Spirit creature tokens"),
    ("Fractal Anomaly", "Instant", "uncommon", "Fractal creature token"),
    ("Snarl Song", "Sorcery", "uncommon", "Fractal creature tokens"),
    ("Send in the Pest", "Sorcery", "common", "Each opponent discards"),
    ("Withering Curse", "Sorcery", "mythic", "-2/-2"),
    ("Social Snub", "Sorcery", "uncommon", "Each player sacrifices"),
    ("Pox Plague", "Sorcery", "rare", "Each player loses half"),
]


class TestRegistryMetadata:
    """Verify registry metadata (type_line, rarity, oracle_text) is accurate."""

    @pytest.mark.parametrize(
        "name,expected_type_line,expected_rarity,oracle_substr",
        _EXPECTED_METADATA,
        ids=[m[0] for m in _EXPECTED_METADATA],
    )
    def test_metadata_accuracy(
        self, name, expected_type_line, expected_rarity, oracle_substr
    ) -> None:
        registry = CardRegistry()
        register_simple_spells_batch2(registry)
        _cls, meta = registry.get(name)

        assert meta.type_line == expected_type_line
        assert meta.rarity == expected_rarity
        assert oracle_substr.lower() in meta.oracle_text.lower()
        assert meta.set_code == "fdn"

    def test_all_spells_have_no_power_toughness(self) -> None:
        """Non-creature spells should have None for power and toughness."""
        registry = CardRegistry()
        register_simple_spells_batch2(registry)
        for name in _EXPECTED_NAMES:
            _cls, meta = registry.get(name)
            assert meta.power is None, f"{name} should have power=None"
            assert meta.toughness is None, f"{name} should have toughness=None"
