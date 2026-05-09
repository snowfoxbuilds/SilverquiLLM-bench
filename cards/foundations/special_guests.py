"""SPG Batch 1 — Simple spells and utility creatures (Special Guest cards).

Implements 5 Special Guest cards from the FDN set:

1. **Condemn** (SPG #74) — {W} instant. Put target attacking creature on the
   bottom of its owner's library. Its controller gains life equal to its
   toughness.
2. **Grim Tutor** (SPG #76) — {1}{B}{B} sorcery. Search your library for a
   card, put it into your hand, then shuffle. You lose 3 life.
3. **Goblin Bushwhacker** (SPG #78) — {R} creature 1/1 Goblin Warrior.
   Kicker {R}. When it enters, if it was kicked, creatures you control get
   +1/+0 and gain haste until end of turn.
4. **Paradise Druid** (SPG #80) — {1}{G} creature 2/1 Elf Druid. Has hexproof
   as long as it's untapped. {T}: Add one mana of any color.
5. **Bloom Tender** (SPG #79) — {1}{G} creature 1/1 Elf Druid. {T}: For each
   color among permanents you control, add one mana of that color.

Use :func:`register_special_guests` to register all cards with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant, ManaAbility, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Color, Keyword, ManaCost, ManaType, Zone

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
