"""SPG Batch 1 & 2 — Special Guest cards from the FDN set.

**Batch 1 — Simple spells and utility creatures:**

1. **Condemn** (SPG #74) — {W} instant.
2. **Grim Tutor** (SPG #76) — {1}{B}{B} sorcery.
3. **Goblin Bushwhacker** (SPG #78) — {R} creature 1/1 Goblin Warrior.
4. **Paradise Druid** (SPG #80) — {1}{G} creature 2/1 Elf Druid.
5. **Bloom Tender** (SPG #79) — {1}{G} creature 1/1 Elf Druid.

**Batch 2 — Complex permanents and spells:**

6. **Sphinx's Tutelage** (SPG #75) — {2}{U} enchantment. Draw-trigger mill.
7. **Embercleave** (SPG #77) — {4}{R}{R} legendary artifact — Equipment.
8. **Akroma's Memorial** (SPG #81) — {7} legendary artifact.
9. **Temporal Manipulation** (SPG #82) — {3}{U}{U} sorcery. Extra turn.
10. **Fiend Artisan** (SPG #83) — {B/G}{B/G} creature */* Nightmare.

Use :func:`register_special_guests` to register all cards with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True


def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition


def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


def _get_colors_of_permanent(obj: Any) -> set[Color]:
    """Return the set of MTG colors for a permanent based on its mana cost."""
    from engine.protection import get_colors
    return get_colors(obj)


# Map Color enum to ManaType for mana production.
_COLOR_TO_MANA: dict[Color, ManaType] = {
    Color.WHITE: ManaType.WHITE,
    Color.BLUE: ManaType.BLUE,
    Color.BLACK: ManaType.BLACK,
    Color.RED: ManaType.RED,
    Color.GREEN: ManaType.GREEN,
}


# ===================================================================
# CONDEMN
# ===================================================================


class Condemn(Instant):
    """Condemn — {W} — Instant

    Put target attacking creature on the bottom of its owner's library.
    Its controller gains life equal to its toughness.

    SPG collector number 74.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Condemn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Put target attacking creature on the bottom of its owner's "
            "library. Its controller gains life equal to its toughness.",
        )
        super().__init__(**kwargs)

    def _get_attacking_creatures(self, game: GameState) -> list[Any]:
        """Return all attacking creatures on the battlefield."""
        targets: list[Any] = []
        for player in game.players:
            bf = game.get_battlefield(player)
            for card in bf.get_all():
                if (
                    CardType.CREATURE in getattr(card, "card_types", set())
                    and getattr(card, "is_attacking", False)
                ):
                    targets.append(card)
        return targets

    def can_cast(self, game: GameState) -> bool:
        """Can only cast when there is at least one attacking creature."""
        return bool(self._get_attacking_creatures(game))

    def get_targets(self, game: GameState) -> list[Any]:
        """Return all attacking creatures as valid targets."""
        return self._get_attacking_creatures(game)

    def on_resolve(self, game: GameState) -> None:
        """Resolve Condemn: bottom-of-library + life gain."""
        chosen = getattr(self, "chosen_targets", None)
        target = chosen[0] if chosen else None
        if target is None:
            return

        # Verify target is still on the battlefield and still attacking
        if not _is_on_battlefield(game, target):
            return
        if not getattr(target, "is_attacking", False):
            return

        controller = getattr(target, "controller", None)
        toughness = getattr(target, "toughness", 0)
        owner = getattr(target, "owner", controller)

        # Move to bottom of owner's library
        # We do a manual zone move since move_to_zone doesn't support
        # position="bottom". Remove from battlefield, add to bottom of library.
        for player in game.players:
            bf = game.get_battlefield(player)
            if bf.contains(target):
                bf.remove(target)
                break

        if owner is not None:
            owner.zones[Zone.LIBRARY].add(target, position="bottom")

        # Fire leaving-battlefield events
        from engine.triggers import EventType
        game.trigger_manager.fire_event(
            game,
            EventType.LEAVES_BATTLEFIELD,
            {"permanent": target, "controller": controller},
        )
        # Unregister triggers
        game.trigger_manager.unregister(target)
        if hasattr(game, "replacement_manager"):
            game.replacement_manager.unregister(target)

        # Controller gains life equal to toughness
        if controller is not None and toughness > 0:
            controller.life += toughness


# ===================================================================
# GRIM TUTOR
# ===================================================================


class GrimTutor(Sorcery):
    """Grim Tutor — {1}{B}{B} — Sorcery

    Search your library for a card, put that card into your hand, then
    shuffle your library. You lose 3 life.

    SPG collector number 76.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Grim Tutor")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Search your library for a card, put that card into your hand, "
            "then shuffle your library. You lose 3 life.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        """Resolve Grim Tutor: search library, put card in hand, shuffle, lose 3 life."""
        controller = self.controller or self.owner
        if controller is None:
            return

        library = controller.zones[Zone.LIBRARY]
        hand = controller.zones[Zone.HAND]

        # Search: pick a card from library via player choice API,
        # or use chosen_targets if pre-set (e.g. by tests).
        chosen = getattr(self, "chosen_targets", None)
        target_card = None

        if chosen and len(chosen) > 0:
            target_card = chosen[0]
        else:
            all_cards = library.get_all()
            if all_cards:
                try:
                    target_card = controller.choose_card(
                        all_cards, "Search your library for a card"
                    )
                except Exception:
                    target_card = all_cards[0]

        if target_card is not None and library.contains(target_card):
            library.remove(target_card)
            hand.add(target_card)

        # Shuffle library
        library.shuffle()

        # Lose 3 life
        controller.life -= 3


# ===================================================================
# GOBLIN BUSHWHACKER
# ===================================================================


class GoblinBushwhacker(Creature):
    """Goblin Bushwhacker — {R} — 1/1 — Goblin Warrior

    Kicker {R}.
    When this creature enters the battlefield, if it was kicked,
    creatures you control get +1/+0 and gain haste until end of turn.

    SPG collector number 78.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Bushwhacker")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Goblin", "Warrior"})
        kwargs.setdefault(
            "rules_text",
            "Kicker {R}\n"
            "When Goblin Bushwhacker enters the battlefield, if it was "
            "kicked, creatures you control get +1/+0 and gain haste "
            "until end of turn.",
        )
        super().__init__(**kwargs)
        self.kicked: bool = False
        self.kicker_cost: ManaCost = ManaCost.parse("{R}")
        self.has_kicker: bool = True

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _etb_effect(g: GameState) -> None:
            if not source.kicked:
                return

            controller = source.controller or source.owner
            if controller is None:
                return

            bf = g.get_battlefield(controller)
            creatures = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
            ]

            # Apply immediately for current state
            for creature in creatures:
                creature.base_power += 1
                creature.keywords = creature.keywords | Keyword.HASTE

            # Register a continuous effect that re-applies during recalculation
            affected = list(creatures)

            def _apply(game_state: Any) -> None:
                for creature in affected:
                    if _is_on_battlefield(game_state, creature):
                        creature.base_power += 1
                        creature.keywords = creature.keywords | Keyword.HASTE

            def _remove(game_state: Any) -> None:
                for creature in affected:
                    if _is_on_battlefield(game_state, creature):
                        creature.base_power -= 1
                        creature.keywords = Keyword(
                            creature.keywords & ~Keyword.HASTE
                        )

            g.effect_manager.add(ContinuousEffect(
                source=source,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply,
                duration=DURATION_END_OF_TURN,
            ))

        reg = TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_etb_effect,
            source=self,
            controller=self.controller or self.owner,
        )
        game.trigger_manager.register(reg)


# ===================================================================
# PARADISE DRUID
# ===================================================================


class ParadiseDruid(Creature):
    """Paradise Druid — {1}{G} — 2/1 — Elf Druid

    Paradise Druid has hexproof as long as it's untapped.
    {T}: Add one mana of any color.

    SPG collector number 80.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Paradise Druid")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault(
            "rules_text",
            "Paradise Druid has hexproof as long as it's untapped.\n"
            "{T}: Add one mana of any color.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        """Register a continuous effect for conditional hexproof."""
        source = self

        def _apply_hexproof(g: Any) -> None:
            """Grant hexproof if untapped, remove it if tapped."""
            if not _is_on_battlefield(g, source):
                return
            if not getattr(source, "is_tapped", False):
                source.keywords = source.keywords | Keyword.HEXPROOF
            else:
                source.keywords = Keyword(source.keywords & ~Keyword.HEXPROOF)

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            apply=_apply_hexproof,
            duration=DURATION_PERMANENT,
        ))

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return mana abilities for any-color mana production."""
        source = self
        abilities: list[ManaAbility] = []

        # One ability per color for "any color" mana
        for color_name, mana_type in [
            ("W", ManaType.WHITE),
            ("U", ManaType.BLUE),
            ("B", ManaType.BLACK),
            ("R", ManaType.RED),
            ("G", ManaType.GREEN),
        ]:
            def _make_effect(mt: ManaType = mana_type) -> Any:
                def _effect(game: Any) -> None:
                    controller = source.controller
                    if controller is not None:
                        controller.mana_pool.add(mt, 1)
                return _effect

            abilities.append(ManaAbility(
                cost=_tap_cost,
                mana_produced=_make_effect(),
                description=f"{{T}}: Add {{{color_name}}}.",
            ))

        return abilities


# ===================================================================
# BLOOM TENDER
# ===================================================================


class BloomTender(Creature):
    """Bloom Tender — {1}{G} — 1/1 — Elf Druid

    {T}: For each color among permanents you control, add one mana of
    that color.

    SPG collector number 79.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bloom Tender")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault(
            "rules_text",
            "{T}: For each color among permanents you control, add one "
            "mana of that color.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is None:
                return

            # Scan all permanents the controller controls on the battlefield
            bf = game.get_battlefield(controller)
            colors_found: set[Color] = set()
            for perm in bf.get_all():
                colors_found |= _get_colors_of_permanent(perm)

            # Add one mana of each color found
            for color in colors_found:
                mana_type = _COLOR_TO_MANA.get(color)
                if mana_type is not None:
                    controller.mana_pool.add(mana_type, 1)

        return [ManaAbility(
            cost=_tap_cost,
            mana_produced=_effect,
            description="{T}: For each color among permanents you control, "
                        "add one mana of that color.",
        )]


# ===========================================================================
# BATCH 2 — Complex permanents and spells
# ===========================================================================


# ===================================================================
# SPHINX'S TUTELAGE
# ===================================================================


class SphinxsTutelage(Enchantment):
    """Sphinx's Tutelage — {2}{U} — Enchantment

    Whenever you draw a card, target opponent mills two cards, then if
    two nonland cards that share a color were milled this way, repeat
    this process.

    {5}{U}: Draw a card, then discard a card.

    SPG collector number 75.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sphinx's Tutelage")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever you draw a card, target opponent mills two cards, "
            "then if two nonland cards that share a color were milled this "
            "way, repeat this process.\n"
            "{5}{U}: Draw a card, then discard a card.",
        )
        super().__init__(**kwargs)

    @staticmethod
    def _mill(game: Any, player: Any, count: int) -> list[Any]:
        """Mill *count* cards from *player*'s library to graveyard.

        Returns the list of milled cards.
        """
        milled: list[Any] = []
        library = player.zones[Zone.LIBRARY]
        graveyard = player.zones[Zone.GRAVEYARD]
        for _ in range(count):
            if len(library) == 0:
                break
            cards = library.top(1)
            card = cards[0]
            library.remove(card)
            graveyard.add(card)
            milled.append(card)
        return milled

    @staticmethod
    def _shared_color_among_nonlands(cards: list[Any]) -> bool:
        """Return True if two nonland cards in *cards* share a colour."""
        nonlands = [
            c for c in cards
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        if len(nonlands) < 2:
            return False
        # Gather colours per nonland card
        color_sets = [_get_colors_of_permanent(c) for c in nonlands]
        # Check pairwise for shared colour
        for i in range(len(color_sets)):
            for j in range(i + 1, len(color_sets)):
                if color_sets[i] & color_sets[j]:
                    return True
        return False

    def register_triggers(self, game: Any) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(g: Any, data: dict) -> bool:
            """Fire when the controller draws a card."""
            controller = source.controller or source.owner
            return data.get("player") is controller

        def _effect(g: Any) -> None:
            controller = source.controller or source.owner
            if controller is None:
                return
            # Target opponent — pick the first opponent
            opponent = None
            for p in g.players:
                if p is not controller:
                    opponent = p
                    break
            if opponent is None:
                return
            # Mill-repeat loop
            max_iterations = 100  # Safety cap
            for _ in range(max_iterations):
                milled = SphinxsTutelage._mill(g, opponent, 2)
                if len(milled) < 2:
                    break
                if not SphinxsTutelage._shared_color_among_nonlands(milled):
                    break

        reg = TriggerRegistration(
            event_type=EventType.DRAWS_CARD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=source.controller or source.owner,
        )
        game.trigger_manager.register(reg)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost.parse("{5}{U}")
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _effect(game: Any) -> None:
            from engine.game import draw_card, discard

            controller = source.controller or source.owner
            if controller is None:
                return
            card_drawn = draw_card(game, controller)
            # Discard: let controller choose, or pick first card in hand
            hand = controller.zones[Zone.HAND]
            cards_in_hand = hand.get_all()
            if cards_in_hand:
                to_discard = cards_in_hand[0]
                discard(game, controller, to_discard)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{5}{U}: Draw a card, then discard a card.",
        )]


# ===================================================================
# EMBERCLEAVE
# ===================================================================


class Embercleave(Artifact):
    """Embercleave — {4}{R}{R} — Legendary Artifact — Equipment

    Flash
    This spell costs {1} less to cast for each attacking creature you
    control.
    When Embercleave enters the battlefield, attach it to target creature
    you control.
    Equipped creature gets +1/+1 and has double strike and trample.
    Equip {3}

    SPG collector number 77.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Embercleave")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{R}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault(
            "rules_text",
            "Flash\n"
            "This spell costs {1} less to cast for each attacking creature "
            "you control.\n"
            "When Embercleave enters the battlefield, attach it to target "
            "creature you control.\n"
            "Equipped creature gets +1/+1 and has double strike and trample.\n"
            "Equip {3}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self._effect_ref: ContinuousEffect | None = None

    def cost_reduction(self, game: Any) -> int:
        """Cost {1} less for each attacking creature you control."""
        controller = self.controller or self.owner
        if controller is None:
            return 0
        count = 0
        bf = game.get_battlefield(controller)
        for perm in bf.get_all():
            if (
                CardType.CREATURE in getattr(perm, "card_types", set())
                and getattr(perm, "is_attacking", False)
            ):
                count += 1
        return count

    def equip(self, target: Any, game: Any) -> None:
        """Attach Embercleave to *target* creature."""
        self.attached_to = target
        self._register_effect(game)

    def _register_effect(self, game: Any) -> None:
        equip_ref = self

        def _apply_keywords(g: Any) -> None:
            if not _is_on_battlefield(g, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(g, creature):
                return
            creature.keywords = (
                creature.keywords | Keyword.DOUBLE_STRIKE | Keyword.TRAMPLE
            )

        def _apply_pt(g: Any) -> None:
            if not _is_on_battlefield(g, equip_ref):
                return
            creature = equip_ref.attached_to
            if creature is None or not _is_on_battlefield(g, creature):
                return
            creature.base_power += 1
            creature.base_toughness += 1

        if self._effect_ref is None:
            # Keywords in Layer 6 (ABILITY)
            effect_kw = ContinuousEffect(
                source=equip_ref,
                layer=Layer.ABILITY,
                sublayer=None,
                apply=_apply_keywords,
                duration=DURATION_PERMANENT,
            )
            game.effect_manager.add(effect_kw)
            # +1/+1 in Layer 7c (MODIFY_PT)
            effect_pt = ContinuousEffect(
                source=equip_ref,
                layer=Layer.POWER_TOUGHNESS,
                sublayer=SubLayer.MODIFY_PT,
                apply=_apply_pt,
                duration=DURATION_PERMANENT,
            )
            self._effect_ref = game.effect_manager.add(effect_pt)

    def _do_etb_attach(self, game: Any) -> None:
        """Perform the ETB attach — find a creature you control and equip it."""
        controller = self.controller or self.owner
        if controller is None:
            return
        bf = game.get_battlefield(controller)
        creatures = [
            c for c in bf.get_all()
            if CardType.CREATURE in getattr(c, "card_types", set())
        ]
        if creatures:
            target = creatures[0]  # Auto-select first creature
            self.equip(target, game)

    def on_resolve(self, game: Any) -> None:
        """When Embercleave resolves, it enters the battlefield and attaches."""
        # The spell moves to battlefield via the casting system; perform
        # the ETB attach directly so it works regardless of trigger
        # registration ordering (ETB fires before register_triggers).
        self._do_etb_attach(game)

    def register_triggers(self, game: Any) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _etb_condition(g: Any, data: dict) -> bool:
            return data.get("permanent") is source

        def _etb_effect(g: Any) -> None:
            source._do_etb_attach(g)

        reg = TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_etb_condition,
            effect=_etb_effect,
            source=self,
            controller=source.controller or source.owner,
        )
        game.trigger_manager.register(reg)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = getattr(src, "controller", None)
            if controller is None:
                return False
            cost = ManaCost(generic=3)
            if not controller.mana_pool.can_pay(cost):
                return False
            controller.mana_pool.pay(cost)
            return True

        def _effect(game: Any) -> None:
            target = getattr(source, "_current_target", None)
            if target is not None:
                source.equip(target, game)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="Equip {3} (sorcery speed)",
        )]


# ===================================================================
# AKROMA'S MEMORIAL
# ===================================================================


class AkromasMemorial(Artifact):
    """Akroma's Memorial — {7} — Legendary Artifact

    Creatures you control have flying, first strike, vigilance, trample,
    haste, and protection from black and from red.

    SPG collector number 81.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Akroma's Memorial")
        kwargs.setdefault("mana_cost", ManaCost.parse("{7}"))
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault(
            "rules_text",
            "Creatures you control have flying, first strike, vigilance, "
            "trample, haste, and protection from black and from red.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: Any) -> None:
        """Register a continuous effect granting keywords and protection."""
        from engine.protection import ProtectionAbility

        source = self

        _KEYWORDS = (
            Keyword.FLYING
            | Keyword.FIRST_STRIKE
            | Keyword.VIGILANCE
            | Keyword.TRAMPLE
            | Keyword.HASTE
        )

        pro_black = ProtectionAbility(quality=Color.BLACK)
        pro_red = ProtectionAbility(quality=Color.RED)

        def _apply(g: Any) -> None:
            if not _is_on_battlefield(g, source):
                return
            controller = source.controller or source.owner
            if controller is None:
                return
            bf = g.get_battlefield(controller)
            for perm in bf.get_all():
                if CardType.CREATURE not in getattr(perm, "card_types", set()):
                    continue
                perm.keywords = perm.keywords | _KEYWORDS
                # Add protection abilities
                if not hasattr(perm, "protections"):
                    perm.protections = []
                # Avoid duplicates by checking quality
                existing_qualities = {
                    p.quality for p in perm.protections
                }
                if Color.BLACK not in existing_qualities:
                    perm.protections.append(pro_black)
                if Color.RED not in existing_qualities:
                    perm.protections.append(pro_red)

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            apply=_apply,
            duration=DURATION_PERMANENT,
        ))


# ===================================================================
# TEMPORAL MANIPULATION
# ===================================================================


class TemporalManipulation(Sorcery):
    """Temporal Manipulation — {3}{U}{U} — Sorcery

    Take an extra turn after this one.

    SPG collector number 82.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Temporal Manipulation")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Take an extra turn after this one.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: Any) -> None:
        """Grant the controller an extra turn."""
        controller = self.controller or self.owner
        if controller is None:
            return
        # Find the controller's player index
        player_index = None
        for i, p in enumerate(game.players):
            if p is controller:
                player_index = i
                break
        if player_index is not None:
            game.extra_turns.append(player_index)


# ===================================================================
# FIEND ARTISAN
# ===================================================================


class FiendArtisan(Creature):
    """Fiend Artisan — {B/G}{B/G} — Creature — Nightmare

    Fiend Artisan's power and toughness are each equal to the number of
    creature cards in your graveyard.

    {X}{B/G}, {T}, Sacrifice another creature: Search your library for
    a creature card with mana value X or less, put it onto the
    battlefield, then shuffle. Activate only as a sorcery.

    SPG collector number 83.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fiend Artisan")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B/G}{B/G}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 0)
        kwargs.setdefault("subtypes", {"Nightmare"})
        kwargs.setdefault(
            "rules_text",
            "Fiend Artisan's power and toughness are each equal to the "
            "number of creature cards in your graveyard.\n"
            "{X}{B/G}, {T}, Sacrifice another creature: Search your library "
            "for a creature card with mana value X or less, put it onto the "
            "battlefield, then shuffle your library. Activate only as a "
            "sorcery.",
        )
        super().__init__(**kwargs)

    def _graveyard_creature_count(self) -> int:
        """Return the number of creature cards in the controller's graveyard."""
        controller = self.controller or self.owner
        if controller is None:
            return 0
        graveyard = controller.zones[Zone.GRAVEYARD]
        count = 0
        for card in graveyard.get_all():
            if CardType.CREATURE in getattr(card, "card_types", set()):
                count += 1
        return count

    @property
    def power(self) -> int:
        """P/T = number of creature cards in your graveyard (CDA)."""
        return self._graveyard_creature_count()

    @property
    def toughness(self) -> int:
        """P/T = number of creature cards in your graveyard (CDA)."""
        return self._graveyard_creature_count()

    def register_triggers(self, game: Any) -> None:
        """Register characteristic-defining ability as a continuous effect."""
        source = self

        def _apply(g: Any) -> None:
            if not _is_on_battlefield(g, source):
                return
            count = source._graveyard_creature_count()
            source.base_power = count
            source.base_toughness = count

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.CHARACTERISTIC_DEFINING,
            apply=_apply,
            duration=DURATION_PERMANENT,
        ))

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            """Pay {X}{B/G}, tap, sacrifice another creature.

            The X value is read from ``src._x_value`` (set by the game
            engine or test harness before calling the ability).
            """
            from engine.casting import is_sorcery_speed

            controller = getattr(src, "controller", None)
            if controller is None:
                return False

            # Sorcery speed only
            if not is_sorcery_speed(game, controller):
                return False

            # Must be untapped
            if getattr(src, "is_tapped", False):
                return False

            # Must have another creature to sacrifice
            bf = game.get_battlefield(controller)
            other_creatures = [
                c for c in bf.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and c is not src
            ]
            if not other_creatures:
                return False

            x_value = getattr(src, "_x_value", 0)

            # Pay {X} generic + {B/G} hybrid (simplified: try B then G)
            # Build the cost: X generic + 1 hybrid {B/G}
            total_generic = x_value
            # Try paying 1 black or 1 green for the hybrid portion
            hybrid_paid = False
            if controller.mana_pool.get(ManaType.BLACK) >= 1:
                if controller.mana_pool.total() >= total_generic + 1:
                    controller.mana_pool.pay(ManaCost(pips={ManaType.BLACK: 1}))
                    hybrid_paid = True
            if not hybrid_paid and controller.mana_pool.get(ManaType.GREEN) >= 1:
                if controller.mana_pool.total() >= total_generic + 1:
                    controller.mana_pool.pay(ManaCost(pips={ManaType.GREEN: 1}))
                    hybrid_paid = True
            if not hybrid_paid:
                return False

            if controller.mana_pool.total() < total_generic:
                return False
            if total_generic > 0:
                controller.mana_pool.pay(ManaCost(generic=total_generic))

            # Tap
            src.is_tapped = True

            # Sacrifice another creature (pick first available)
            sac_target = getattr(src, "_sacrifice_target", None)
            if sac_target is None:
                sac_target = other_creatures[0]
            if bf.contains(sac_target):
                from engine.zones import move_to_zone
                move_to_zone(game, sac_target, Zone.BATTLEFIELD, Zone.GRAVEYARD)

            return True

        def _effect(game: Any) -> None:
            controller = source.controller or source.owner
            if controller is None:
                return
            x_value = getattr(source, "_x_value", 0)
            library = controller.zones[Zone.LIBRARY]

            # Search for a creature with MV <= X
            candidates = [
                c for c in library.get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
                and _get_mana_value(c) <= x_value
            ]

            if candidates:
                # Let controller choose, or pick first
                chosen = candidates[0]
                if hasattr(controller, "choose_card"):
                    try:
                        chosen = controller.choose_card(
                            candidates,
                            f"Search for creature with MV ≤ {x_value}",
                        )
                    except Exception:
                        chosen = candidates[0]
                library.remove(chosen)
                chosen.owner = chosen.owner or controller
                chosen.controller = controller
                from engine.zones import move_to_zone
                # Place onto battlefield from library
                # Directly add to battlefield since move_to_zone expects
                # the card to be in the source zone
                game.get_battlefield(controller).add(chosen)
                if hasattr(chosen, "register_triggers"):
                    chosen.register_triggers(game)
                from engine.triggers import EventType
                game.trigger_manager.fire_event(
                    game,
                    EventType.ENTERS_BATTLEFIELD,
                    {"permanent": chosen, "controller": controller},
                )

            # Shuffle library
            library.shuffle()

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{X}{B/G}, {T}, Sacrifice another creature: "
                        "Search your library for a creature card with mana "
                        "value X or less, put it onto the battlefield, then "
                        "shuffle. Activate only as a sorcery.",
        )]


def _get_mana_value(card: Any) -> int:
    """Return the mana value (converted mana cost) of a card."""
    mc = getattr(card, "mana_cost", None)
    if mc is None:
        return 0
    total = getattr(mc, "generic", 0)
    pips = getattr(mc, "pips", {})
    for count in pips.values():
        total += count
    # Hybrid symbols: each hybrid symbol contributes 1 to mana value
    hybrid = getattr(mc, "hybrid", [])
    total += len(hybrid)
    return total


# ===========================================================================
# Registration
# ===========================================================================

_ALL_SPECIAL_GUESTS: list[tuple[str, type, dict[str, Any]]] = [
    ("Condemn", Condemn, {
        "collector_number": "74", "rarity": "rare",
        "mana_cost_str": "{W}", "type_line": "Instant",
        "colors": ["W"],
        "oracle_text": "Put target attacking creature on the bottom of its "
                       "owner's library. Its controller gains life equal to "
                       "its toughness.",
    }),
    ("Grim Tutor", GrimTutor, {
        "collector_number": "76", "rarity": "mythic",
        "mana_cost_str": "{1}{B}{B}", "type_line": "Sorcery",
        "colors": ["B"],
        "oracle_text": "Search your library for a card, put that card into "
                       "your hand, then shuffle your library. You lose 3 life.",
    }),
    ("Goblin Bushwhacker", GoblinBushwhacker, {
        "collector_number": "78", "rarity": "rare",
        "mana_cost_str": "{R}", "type_line": "Creature — Goblin Warrior",
        "power": "1", "toughness": "1", "colors": ["R"],
        "keywords": ["Kicker"],
        "oracle_text": "Kicker {R}\nWhen Goblin Bushwhacker enters the "
                       "battlefield, if it was kicked, creatures you control "
                       "get +1/+0 and gain haste until end of turn.",
    }),
    ("Bloom Tender", BloomTender, {
        "collector_number": "79", "rarity": "mythic",
        "mana_cost_str": "{1}{G}", "type_line": "Creature — Elf Druid",
        "power": "1", "toughness": "1", "colors": ["G"],
        "oracle_text": "{T}: For each color among permanents you control, "
                       "add one mana of that color.",
    }),
    ("Paradise Druid", ParadiseDruid, {
        "collector_number": "80", "rarity": "rare",
        "mana_cost_str": "{1}{G}", "type_line": "Creature — Elf Druid",
        "power": "2", "toughness": "1", "colors": ["G"],
        "oracle_text": "Paradise Druid has hexproof as long as it's untapped.\n"
                       "{T}: Add one mana of any color.",
    }),
    # --- Batch 2 ---
    ("Sphinx's Tutelage", SphinxsTutelage, {
        "collector_number": "75", "rarity": "rare",
        "mana_cost_str": "{2}{U}", "type_line": "Enchantment",
        "colors": ["U"],
        "oracle_text": "Whenever you draw a card, target opponent mills two "
                       "cards, then if two nonland cards that share a color "
                       "were milled this way, repeat this process.\n"
                       "{5}{U}: Draw a card, then discard a card.",
    }),
    ("Embercleave", Embercleave, {
        "collector_number": "77", "rarity": "mythic",
        "mana_cost_str": "{4}{R}{R}", "type_line": "Legendary Artifact — Equipment",
        "colors": ["R"],
        "keywords": ["Flash"],
        "oracle_text": "Flash\nThis spell costs {1} less to cast for each "
                       "attacking creature you control.\nWhen Embercleave "
                       "enters the battlefield, attach it to target creature "
                       "you control.\nEquipped creature gets +1/+1 and has "
                       "double strike and trample.\nEquip {3}",
    }),
    ("Akroma's Memorial", AkromasMemorial, {
        "collector_number": "81", "rarity": "mythic",
        "mana_cost_str": "{7}", "type_line": "Legendary Artifact",
        "colors": [],
        "keywords": [],
        "oracle_text": "Creatures you control have flying, first strike, "
                       "vigilance, trample, haste, and protection from black "
                       "and from red.",
    }),
    ("Temporal Manipulation", TemporalManipulation, {
        "collector_number": "82", "rarity": "mythic",
        "mana_cost_str": "{3}{U}{U}", "type_line": "Sorcery",
        "colors": ["U"],
        "oracle_text": "Take an extra turn after this one.",
    }),
    ("Fiend Artisan", FiendArtisan, {
        "collector_number": "83", "rarity": "mythic",
        "mana_cost_str": "{B/G}{B/G}", "type_line": "Creature — Nightmare",
        "power": "*", "toughness": "*", "colors": ["B", "G"],
        "oracle_text": "Fiend Artisan's power and toughness are each equal "
                       "to the number of creature cards in your graveyard.\n"
                       "{X}{B/G}, {T}, Sacrifice another creature: Search "
                       "your library for a creature card with mana value X "
                       "or less, put it onto the battlefield, then shuffle. "
                       "Activate only as a sorcery.",
    }),
]


def register_special_guests(registry: CardRegistry) -> None:
    """Register all Special Guest cards with *registry*."""
    from cards.registry import CardMetadata

    for card_name, impl_class, meta_kwargs in _ALL_SPECIAL_GUESTS:
        metadata = CardMetadata(
            name=card_name,
            set_code="spg",
            **meta_kwargs,
        )
        registry.register(card_name, impl_class, metadata)
