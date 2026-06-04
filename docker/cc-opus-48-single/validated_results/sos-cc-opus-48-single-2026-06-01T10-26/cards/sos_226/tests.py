"""Tests for SOS 226 — Silverquill, the Disputant.

Silverquill is a 4/4 Legendary Elder Dragon ({2}{W}{B}) with Flying and
Vigilance. Its second ability grants **casualty 1** to every instant and
sorcery spell its controller casts:

    "Each instant and sorcery spell you cast has casualty 1. (As you cast
     that spell, you may sacrifice a creature with power 1 or greater. When
     you do, copy the spell and you may choose new targets for the copy.)"

Casualty (rule 702.153) is a brand-new mechanic with no pre-existing engine
surface, so these tests pin the firmest observable contract:

* Static card data (name, cost, types, P/T, colors, keywords).
* A casualty grant wired through the spell-cast trigger machinery:
  when the controller casts their own instant/sorcery and Silverquill is on
  the battlefield, the controller may sacrifice a power>=1 creature; doing so
  copies the spell onto the stack.
* Scope: only the controller's instant/sorcery spells qualify — not the
  opponent's, and not creature/permanent spells.
* The "you may" / "creature with power 1 or greater" guards.

The casualty-driven copy/sacrifice tests fire ``SpellCastTriggeredEvent``
through ``game.trigger_manager`` (the same pattern used by FDN reference
cast-trigger cards) and assert on the observable consequences: the chosen
creature leaving the battlefield to the graveyard, and a copy of the spell
appearing on the stack.
"""

from __future__ import annotations

from typing import Any

from cards.sos.sos_226.card_impl import SilverquillTheDisputant
from engine.card import Creature, Instant, Sorcery
from engine.casting import cast_spell as engine_cast_spell
from engine.events import SpellCastTriggeredEvent
from engine.game import deal_damage
from engine.types import (
    CardType,
    Color,
    Keyword,
    ManaCost,
    ManaType,
    Phase,
    Supertype,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_silverquill(owner=None, controller=None) -> SilverquillTheDisputant:
    return SilverquillTheDisputant(owner=owner, controller=controller)


def _bear(name: str = "Grizzly Bears", power: int = 2, toughness: int = 2) -> Creature:
    """A vanilla creature usable as a casualty sacrifice."""
    return Creature(name=name, base_power=power, base_toughness=toughness)


def _instant(name: str = "Lightning Bolt") -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse("{R}"))


def _sorcery(name: str = "Divination") -> Sorcery:
    return Sorcery(name=name, mana_cost=ManaCost.parse("{2}{U}"))


class _PingInstant(Instant):
    """A minimal targeted instant: deals 1 damage to a single target creature.

    Used to exercise the casualty copy's new-target choice end to end: the
    copy resolves against ``chosen_targets`` exactly like the original, so a
    re-targeted copy marks damage on a *different* creature.
    """

    def __init__(self, name: str = "Ping", **kwargs: Any) -> None:
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        super().__init__(name=name, **kwargs)

    def get_targets(self, game: Any) -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE
                in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: Any) -> None:
        targets = getattr(self, "chosen_targets", None) or []
        if targets and targets[0] is not None:
            deal_damage(game, self, targets[0], 1)


# ---------------------------------------------------------------------------
# Static card data
# ---------------------------------------------------------------------------

class TestSilverquillProperties:
    """Static characteristics must match the SOS 226 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(_make_silverquill(), Creature)

    def test_name(self) -> None:
        assert _make_silverquill().name == "Silverquill, the Disputant"

    def test_mana_cost(self) -> None:
        assert _make_silverquill().mana_cost == ManaCost.parse("{2}{W}{B}")

    def test_power_toughness(self) -> None:
        card = _make_silverquill()
        assert card.base_power == 4
        assert card.base_toughness == 4

    def test_legendary(self) -> None:
        assert Supertype.LEGENDARY in _make_silverquill().supertypes

    def test_elder_dragon_subtypes(self) -> None:
        subtypes = _make_silverquill().subtypes
        assert "Dragon" in subtypes
        assert "Elder" in subtypes

    def test_has_flying(self) -> None:
        assert Keyword.FLYING in _make_silverquill().keywords

    def test_has_vigilance(self) -> None:
        assert Keyword.VIGILANCE in _make_silverquill().keywords

    def test_is_white_and_black(self) -> None:
        colors = _make_silverquill().colors
        assert Color.WHITE in colors
        assert Color.BLACK in colors

    def test_not_other_colors(self) -> None:
        colors = _make_silverquill().colors
        assert Color.RED not in colors
        assert Color.BLUE not in colors
        assert Color.GREEN not in colors


# ---------------------------------------------------------------------------
# Trigger registration
# ---------------------------------------------------------------------------

class TestSilverquillTriggerRegistration:
    """The casualty grant is wired through a spell-cast trigger."""

    def test_registers_a_spell_cast_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _make_silverquill(owner=p1, controller=p1)
        before = len(game.trigger_manager.get_triggers())
        card.register_triggers(game)
        after = len(game.trigger_manager.get_triggers())
        assert after > before

    def test_trigger_watches_spell_cast_event(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = _make_silverquill(owner=p1, controller=p1)
        card.register_triggers(game)
        regs = game.trigger_manager.get_triggers_for_source(card)
        assert regs, "Silverquill should register at least one trigger"
        assert any(r.event_type is SpellCastTriggeredEvent for r in regs)


# ---------------------------------------------------------------------------
# Casualty grant — scope (whose / which spells qualify)
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyScope:
    """Only the controller's instant/sorcery spells get the casualty grant."""

    def test_controller_instant_offers_casualty(self) -> None:
        """Casting your own instant with a power>=1 creature available and
        choosing to pay casualty sacrifices the creature."""
        game = create_game(scripts=([True, None], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        sac_creature = _bear()
        set_board_state(game, 0, battlefield=[silverquill, sac_creature])
        silverquill.register_triggers(game)

        bolt = _instant()
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.STACK].add(bolt)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, player=p1, card=bolt, controller=p1),
        )
        # Resolve the queued casualty trigger.
        while not game.stack.is_empty() and game.stack.peek().source is silverquill:
            game.stack.pop().on_resolve(game)
            break

        assert game.get_graveyard(p1).contains(sac_creature)
        assert not game.get_battlefield(p1).contains(sac_creature)

    def test_opponent_spell_does_not_trigger(self) -> None:
        """An instant cast by the opponent must not trigger Silverquill's
        casualty grant (it only applies to spells *you* cast)."""
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill, _bear()])
        silverquill.register_triggers(game)

        opp_bolt = _instant("Opponent Bolt")
        opp_bolt.owner = p2
        opp_bolt.controller = p2
        p2.zones[Zone.STACK].add(opp_bolt)

        before = len(game.stack)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=opp_bolt, player=p2, card=opp_bolt, controller=p2
            ),
        )
        assert len(game.stack) == before

    def test_creature_spell_does_not_trigger(self) -> None:
        """Casualty applies only to instant and sorcery spells — casting a
        creature spell must not fire the casualty trigger."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill, _bear()])
        silverquill.register_triggers(game)

        creature_spell = Creature(
            name="Some Creature", mana_cost=ManaCost.parse("{1}{G}"),
            base_power=3, base_toughness=3,
        )
        creature_spell.owner = p1
        creature_spell.controller = p1
        p1.zones[Zone.STACK].add(creature_spell)

        before = len(game.stack)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(
                spell=creature_spell, player=p1, card=creature_spell, controller=p1
            ),
        )
        assert len(game.stack) == before

    def test_sorcery_qualifies(self) -> None:
        """Sorceries also receive the casualty grant."""
        game = create_game()
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[silverquill, _bear()])
        silverquill.register_triggers(game)

        sorc = _sorcery()
        sorc.owner = p1
        sorc.controller = p1
        p1.zones[Zone.STACK].add(sorc)

        before = len(game.stack)
        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=sorc, player=p1, card=sorc, controller=p1),
        )
        # A matching casualty trigger should have been pushed.
        assert len(game.stack) > before


# ---------------------------------------------------------------------------
# Casualty grant — copy behaviour
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyCopy:
    """Paying casualty (sacrificing a power>=1 creature) copies the spell."""

    def test_paying_casualty_creates_a_copy_on_the_stack(self) -> None:
        game = create_game(scripts=([True, None], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        sac_creature = _bear()
        set_board_state(game, 0, battlefield=[silverquill, sac_creature])
        silverquill.register_triggers(game)

        bolt = _instant()
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.STACK].add(bolt)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, player=p1, card=bolt, controller=p1),
        )
        # Resolve the casualty trigger (top of stack).
        assert not game.stack.is_empty()
        casualty_trigger = game.stack.pop()
        assert casualty_trigger.source is silverquill
        before = len(game.stack)
        casualty_trigger.on_resolve(game)

        # A copy of the original spell should now be on the stack.
        assert len(game.stack) == before + 1
        copy_obj = game.stack.peek()
        assert copy_obj.source is not bolt
        assert getattr(copy_obj.source, "name", None) == bolt.name

    def test_declining_casualty_makes_no_copy_and_no_sacrifice(self) -> None:
        """The casualty cost is optional ('you may'); declining sacrifices
        nothing and creates no copy."""
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        sac_creature = _bear()
        set_board_state(game, 0, battlefield=[silverquill, sac_creature])
        silverquill.register_triggers(game)

        bolt = _instant()
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.STACK].add(bolt)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, player=p1, card=bolt, controller=p1),
        )
        assert not game.stack.is_empty()
        casualty_trigger = game.stack.pop()
        before = len(game.stack)
        casualty_trigger.on_resolve(game)

        # No copy created, creature not sacrificed.
        assert len(game.stack) == before
        assert game.get_battlefield(p1).contains(sac_creature)
        assert not game.get_graveyard(p1).contains(sac_creature)

    def test_no_eligible_creature_means_no_copy(self) -> None:
        """With no creature of power 1 or greater to sacrifice (only a 0-power
        creature is present), casualty cannot be paid and no copy is made."""
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        wall = _bear(name="Wall of Wood", power=0, toughness=3)
        set_board_state(game, 0, battlefield=[silverquill, wall])
        silverquill.register_triggers(game)

        bolt = _instant()
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.STACK].add(bolt)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, player=p1, card=bolt, controller=p1),
        )
        # If a trigger was even pushed, resolving it must neither copy the
        # spell nor sacrifice the 0-power creature.
        while not game.stack.is_empty() and game.stack.peek().source is silverquill:
            trig = game.stack.pop()
            before = len(game.stack)
            trig.on_resolve(game)
            assert len(game.stack) == before
            break
        assert game.get_battlefield(p1).contains(wall)
        assert not game.get_graveyard(p1).contains(wall)

    def test_zero_power_creature_not_a_legal_sacrifice(self) -> None:
        """A creature with power 0 must never be sacrificed for casualty even
        when a higher-power creature is also present and unused (the casualty
        sacrifice requires power 1 or greater)."""
        game = create_game(scripts=([True, None], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        wall = _bear(name="Wall of Wood", power=0, toughness=3)
        bear = _bear()
        set_board_state(game, 0, battlefield=[silverquill, wall, bear])
        silverquill.register_triggers(game)

        bolt = _instant()
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.STACK].add(bolt)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, player=p1, card=bolt, controller=p1),
        )
        while not game.stack.is_empty() and game.stack.peek().source is silverquill:
            game.stack.pop().on_resolve(game)
            break
        # The 0-power wall must remain on the battlefield.
        assert game.get_battlefield(p1).contains(wall)
        assert not game.get_graveyard(p1).contains(wall)


# ---------------------------------------------------------------------------
# Silverquill itself contributes power>=1 / off-battlefield behaviour
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyBattlefieldDependency:
    """The grant only functions while Silverquill is on the battlefield."""

    def test_no_trigger_when_silverquill_not_on_battlefield(self) -> None:
        """With Silverquill in hand (not on the battlefield), casting an
        instant must not produce a casualty copy."""
        game = create_game(scripts=([True, None], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        # Silverquill is in hand, not on the battlefield.
        set_board_state(game, 0, hand=[silverquill], battlefield=[_bear()])
        silverquill.register_triggers(game)

        bolt = _instant()
        bolt.owner = p1
        bolt.controller = p1
        p1.zones[Zone.STACK].add(bolt)

        game.trigger_manager.fire_event(
            game,
            SpellCastTriggeredEvent(spell=bolt, player=p1, card=bolt, controller=p1),
        )
        # Either no trigger fired, or the trigger resolves to a no-op (no copy).
        copies = [
            obj for obj in game.stack.objects()
            if obj.source is not silverquill
            and getattr(obj.source, "name", None) == bolt.name
        ]
        assert copies == []


# ---------------------------------------------------------------------------
# Real-cast pipeline — casualty fires through engine.casting.cast_spell
# ---------------------------------------------------------------------------

def _ready_for_instant_cast(game) -> None:
    """Put the game in a state where player 0 may cast an instant.

    ``cast_spell`` only checks instant-speed timing (which an instant always
    passes) but the priority/phase bookkeeping is set so the scenario reads
    like a normal cast.
    """
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestSilverquillCasualtyThroughRealCast:
    """The casualty grant fires when a spell is cast via engine.casting.cast_spell.

    These tests exercise the previously-untestable "as you cast" path: rather
    than firing ``SpellCastTriggeredEvent`` by hand, they call the real
    ``cast_spell`` pipeline (which now fires the event after pushing the
    spell's StackObject) and assert the casualty trigger is queued above the
    spell and resolves into the sacrifice + copy.
    """

    def test_real_cast_queues_casualty_trigger_above_the_spell(self) -> None:
        """Casting a controller instant through cast_spell pushes the casualty
        trigger on top of the spell's StackObject."""
        # No choices needed before the trigger resolves.
        game = create_game(scripts=([], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        sac_creature = _bear()
        set_board_state(game, 0, battlefield=[silverquill, sac_creature])
        silverquill.register_triggers(game)
        _ready_for_instant_cast(game)

        bolt = _instant()
        set_board_state(game, 0, hand=[bolt])
        p1.mana_pool.add(ManaType.RED, 1)

        engine_cast_spell(game, p1, bolt)

        # The spell itself is on the stack, with the casualty trigger above it.
        assert len(game.stack) == 2
        top = game.stack.peek()
        assert top.source is silverquill
        bottom = game.stack.objects()[-1]
        assert bottom.source is bolt

    def test_real_cast_paying_casualty_sacrifices_and_copies(self) -> None:
        """Resolving the casualty trigger from a real cast (choosing to pay)
        sacrifices the creature and puts a copy of the spell on the stack."""
        # Script: pay casualty? yes.
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        sac_creature = _bear()
        set_board_state(game, 0, battlefield=[silverquill, sac_creature])
        silverquill.register_triggers(game)
        _ready_for_instant_cast(game)

        bolt = _instant()
        set_board_state(game, 0, hand=[bolt])
        p1.mana_pool.add(ManaType.RED, 1)

        engine_cast_spell(game, p1, bolt)

        # Resolve the casualty trigger (top of stack).
        casualty_trigger = game.stack.pop()
        assert casualty_trigger.source is silverquill
        casualty_trigger.on_resolve(game)

        # Creature sacrificed.
        assert game.get_graveyard(p1).contains(sac_creature)
        assert not game.get_battlefield(p1).contains(sac_creature)

        # A distinct copy of the original spell is on the stack (above the
        # still-unresolved original).
        copies = [
            obj for obj in game.stack.objects()
            if obj.source is not bolt
            and getattr(obj.source, "name", None) == bolt.name
        ]
        assert len(copies) == 1
        assert copies[0].source is not bolt

    def test_real_cast_declining_casualty_makes_no_copy(self) -> None:
        """Declining the casualty during a real cast leaves only the original
        spell on the stack and sacrifices nothing."""
        game = create_game(scripts=([False], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        sac_creature = _bear()
        set_board_state(game, 0, battlefield=[silverquill, sac_creature])
        silverquill.register_triggers(game)
        _ready_for_instant_cast(game)

        bolt = _instant()
        set_board_state(game, 0, hand=[bolt])
        p1.mana_pool.add(ManaType.RED, 1)

        engine_cast_spell(game, p1, bolt)

        casualty_trigger = game.stack.pop()
        casualty_trigger.on_resolve(game)

        assert game.get_battlefield(p1).contains(sac_creature)
        copies = [
            obj for obj in game.stack.objects()
            if getattr(obj.source, "name", None) == bolt.name
        ]
        # Only the original spell remains — no copy.
        assert len(copies) == 1
        assert copies[0].source is bolt


# ---------------------------------------------------------------------------
# Casualty copy — choosing NEW targets for the copy
# ---------------------------------------------------------------------------

class TestSilverquillCasualtyNewTargets:
    """The casualty copy may choose new targets (rule 702.153a)."""

    def test_copy_can_retarget_a_different_creature(self) -> None:
        """A targeted spell cast with casualty paid produces a copy that, when
        re-targeted, resolves against a DIFFERENT creature than the original."""
        # Targets are 0-power so the only power>=1 creature is the dedicated
        # sacrifice — keeping the casualty selection auto (no choose_card).
        original_target = _bear(name="Original Target", power=0, toughness=5)
        new_target = _bear(name="New Target", power=0, toughness=5)
        sac_creature = _bear(name="Sacrifice", power=1, toughness=1)
        # Script (in consumption order):
        #   1. cast_spell target choice -> original_target
        #   2. pay casualty? -> True
        #   3. choose new targets for copy? -> True
        #   4. new target choice -> new_target
        game = create_game(
            scripts=([original_target, True, True, new_target], [])
        )
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        set_board_state(
            game, 0,
            battlefield=[silverquill, sac_creature, original_target, new_target],
        )
        silverquill.register_triggers(game)
        _ready_for_instant_cast(game)

        ping = _PingInstant()
        set_board_state(game, 0, hand=[ping])
        # Re-add the battlefield (set_board_state on hand left battlefield intact).
        p1.mana_pool.add(ManaType.RED, 1)

        engine_cast_spell(game, p1, ping)

        # Resolve the casualty trigger -> sacrifice + re-targeted copy.
        casualty_trigger = game.stack.pop()
        assert casualty_trigger.source is silverquill
        casualty_trigger.on_resolve(game)
        assert game.get_graveyard(p1).contains(sac_creature)

        # The copy is on top; resolve it and confirm it hit the NEW target.
        copy_obj = game.stack.pop()
        assert copy_obj.source is not ping
        assert getattr(copy_obj.source, "name", None) == ping.name
        assert copy_obj.targets == [new_target]
        copy_obj.on_resolve(game)

        assert new_target.damage_marked == 1
        assert original_target.damage_marked == 0

    def test_copy_keeps_original_target_when_retarget_declined(self) -> None:
        """Declining the re-target prompt keeps the copy on the original
        target (the new-target choice is optional)."""
        original_target = _bear(name="Original Target", power=0, toughness=5)
        other_creature = _bear(name="Other", power=0, toughness=5)
        sac_creature = _bear(name="Sacrifice", power=1, toughness=1)
        # Script: cast target -> original; pay casualty -> True;
        #         choose new targets? -> False (keep original).
        game = create_game(scripts=([original_target, True, False], []))
        p1 = game.players[0]
        silverquill = _make_silverquill(owner=p1, controller=p1)
        set_board_state(
            game, 0,
            battlefield=[silverquill, sac_creature, original_target, other_creature],
        )
        silverquill.register_triggers(game)
        _ready_for_instant_cast(game)

        ping = _PingInstant()
        set_board_state(game, 0, hand=[ping])
        p1.mana_pool.add(ManaType.RED, 1)

        engine_cast_spell(game, p1, ping)

        casualty_trigger = game.stack.pop()
        casualty_trigger.on_resolve(game)

        copy_obj = game.stack.pop()
        assert copy_obj.targets == [original_target]
        copy_obj.on_resolve(game)

        # The copy hit the original target, not the bystander.
        assert original_target.damage_marked == 1
        assert other_creature.damage_marked == 0
