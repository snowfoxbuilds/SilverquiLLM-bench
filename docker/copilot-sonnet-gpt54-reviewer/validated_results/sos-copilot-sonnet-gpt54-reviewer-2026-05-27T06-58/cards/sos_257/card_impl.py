"""Card implementation for Great Hall of the Biblioplex."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.types import CardType, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


class GreatHallOfTheBiblioplex(Land):
    """{T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color.
    # UNVERIFIED: "Spend this mana only to cast an instant or sorcery" — restricted mana not enforced
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    'Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.'
    # UNVERIFIED: "+1/+0 until end of turn" — EOT reset not tested
    It's still a land.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. "
            "Spend this mana only to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with "
            "'Whenever you cast an instant or sorcery spell, this creature gets +1/+0 until end of turn.' "
            "It's still a land.",
        )
        super().__init__(**kwargs)
        # Persistent animation flag — survives effect recalculation
        self._animated: bool = False
        # Creature-land state (populated when animated)
        self.base_power: int = 0
        self.base_toughness: int = 0
        self.modified_power: int = 0
        self.modified_toughness: int = 0
        self.power_bonus: int = 0
        # Full creature interface fields (populated when animated)
        self.damage_marked: int = 0
        self.summoning_sick: bool = False
        self.is_attacking: bool = False
        self.is_blocking: bool = False
        self.plus_one_counters: int = 0
        self.minus_one_counters: int = 0
        self.is_token: bool = False
        self.dealt_deathtouch_damage: bool = False
        self.colors: set[str] | None = None

    # ------------------------------------------------------------------
    # Creature interface properties (active when animated)
    # ------------------------------------------------------------------

    @property
    def power(self) -> int:
        """Current power including counter modifications (only meaningful when animated)."""
        return self.modified_power + self.plus_one_counters - self.minus_one_counters

    @property
    def toughness(self) -> int:
        """Current toughness including counter modifications (only meaningful when animated)."""
        return self.modified_toughness + self.plus_one_counters - self.minus_one_counters

    def _reset_characteristics(self) -> None:
        """Reset characteristics — preserve animation state if _animated is True."""
        super()._reset_characteristics()
        if self._animated:
            # Re-add CREATURE type so animation survives effect recalculation
            self.card_types.add(CardType.CREATURE)
            # Reset modified stats to base values (continuous effects re-apply on top)
            self.modified_power = self.base_power
            self.modified_toughness = self.base_toughness

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return the two mana abilities of this land."""
        return [
            self._make_colorless_mana_ability(),
            self._make_colored_mana_ability(),
        ]

    def _make_colorless_mana_ability(self) -> ManaAbility:
        """Create the {T}: Add {C} mana ability."""
        source = self

        def cost(game: "GameState", card: Any = None) -> bool:
            target = card if card is not None else source
            if getattr(target, "is_tapped", False):
                return False
            target.is_tapped = True
            return True

        def mana_produced(game: "GameState") -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return ManaAbility(
            cost=cost,
            mana_produced=mana_produced,
            description="{T}: Add {C}.",
        )

    def _make_colored_mana_ability(self) -> ManaAbility:
        """Create the {T}, Pay 1 life: Add one mana of any color ability."""
        source = self

        def cost(game: "GameState", card: Any = None) -> bool:
            target = card if card is not None else source
            # Check tap FIRST — life is only paid if tap succeeds
            if getattr(target, "is_tapped", False):
                return False
            controller = source.controller
            if controller is None:
                return False
            target.is_tapped = True
            controller.life -= 1
            return True

        def mana_produced(game: "GameState") -> None:
            # UNVERIFIED: "Spend this mana only to cast an instant or sorcery" — restricted mana not enforced
            controller = source.controller
            if controller is not None:
                color_options = [
                    ManaType.WHITE, ManaType.BLUE, ManaType.BLACK,
                    ManaType.RED, ManaType.GREEN,
                ]
                try:
                    chosen_color = controller.choose(
                        color_options,
                        "Choose a color of mana to produce",
                    )
                except Exception:
                    # Fallback: default to White when no choice is scripted
                    # (e.g. in unit tests that only verify mana was added)
                    chosen_color = color_options[0]
                controller.mana_pool.add(chosen_color, 1)

        return ManaAbility(
            cost=cost,
            mana_produced=mana_produced,
            description="{T}, Pay 1 life: Add one mana of any color.",
        )

    # ------------------------------------------------------------------
    # Activated abilities
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        """Return activated abilities — {5}: animate this land."""
        return [self._make_animate_ability()]

    def _make_animate_ability(self) -> ActivatedAbility:
        """Create the {5} animate ability."""
        source = self

        def cost(game: "GameState") -> bool:
            controller = source.controller
            if controller is None:
                return False
            from engine.types import ManaCost
            mc = ManaCost.parse("{5}")
            return controller.mana_pool.pay(mc)

        def effect(game: "GameState") -> None:
            # Guard: if already animated as a creature, do nothing
            if source._animated:
                return
            # Animate the land into a 2/4 Wizard creature-land
            source._animated = True
            source.card_types.add(CardType.CREATURE)
            # Update _original_card_types so the animation persists through
            # effect recalculation (EffectManager resets to _original_card_types)
            source._original_card_types = frozenset(source.card_types)
            source.subtypes.add("Wizard")
            source.base_power = 2
            source.base_toughness = 4
            source.modified_power = 2
            source.modified_toughness = 4
            # Initialize full creature interface fields
            source.damage_marked = 0
            source.summoning_sick = True
            source.is_attacking = False
            source.is_blocking = False
            source.plus_one_counters = 0
            source.minus_one_counters = 0

        return ActivatedAbility(
            cost=cost,
            effect=effect,
            description="{5}: If this land isn't a creature, it becomes a 2/4 Wizard creature.",
        )

    # ------------------------------------------------------------------
    # Triggered abilities
    # ------------------------------------------------------------------

    def register_triggers(self, game: "GameState") -> None:
        """Register triggered abilities — only when animated as a creature."""
        if not self._animated:
            return

        from engine.events import SpellCastTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def condition(game: "GameState", event: Any) -> bool:
            # Must be cast by our controller
            if event.controller is not source.controller:
                return False
            # Must be an instant or sorcery
            spell = event.spell or event.card
            if spell is None:
                return False
            spell_types = getattr(spell, "card_types", set())
            return CardType.INSTANT in spell_types or CardType.SORCERY in spell_types

        def effect(game: "GameState") -> None:
            # +1/+0 until end of turn
            # UNVERIFIED: "+1/+0 until end of turn" — EOT reset not tested
            source.modified_power += 1

        controller = self.controller or (game.active_player if game is not None else None)

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=SpellCastTriggeredEvent,
                condition=condition,
                effect=effect,
                source=self,
                controller=controller,
            )
        )
