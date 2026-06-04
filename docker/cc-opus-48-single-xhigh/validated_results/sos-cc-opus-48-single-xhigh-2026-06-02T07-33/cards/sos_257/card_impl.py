"""Card implementation for Great Hall of the Biblioplex.

Great Hall of the Biblioplex — Land:

    {T}: Add {C}.
    {T}, Pay 1 life: Add one mana of any color.  Spend this mana only to cast
    an instant or sorcery spell.
    {5}: If this land isn't a creature, it becomes a 2/4 Wizard creature with
    "Whenever you cast an instant or sorcery spell, this creature gets +1/+0
    until end of turn."  It's still a land.

SOS collector number 257.

The "spend this mana only to cast an instant or sorcery spell" restriction, the
becomes-a-creature animation, and the granted instant/sorcery pump trigger are
all built on additive engine mechanisms:

* restricted mana — :func:`engine.mana.ManaPool.add_restricted` plus the
  spend-restriction check in :func:`engine.casting.cast_spell`;
* land animation — :func:`engine.animation.animate_land`;
* the granted pump trigger — :func:`engine.animation.register_instant_sorcery_pump`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.animation import (
    animate_land,
    is_animated,
    register_instant_sorcery_pump,
)
from engine.card import ActivatedAbility, Land, ManaAbility
from engine.mana import RESTRICT_INSTANT_SORCERY
from engine.types import Color, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


#: The animated body printed on Great Hall of the Biblioplex.
_ANIMATED_POWER = 2
_ANIMATED_TOUGHNESS = 4
_ANIMATED_SUBTYPE = "Wizard"

#: The activation cost of the animation ability.
_ANIMATE_COST = ManaCost(generic=5)

# Map a chosen Color to its corresponding ManaType (the any-color producer
# lets the controller pick any one of the five colors).
_COLOR_TO_MANA: dict[Color, ManaType] = {
    Color.WHITE: ManaType.WHITE,
    Color.BLUE: ManaType.BLUE,
    Color.BLACK: ManaType.BLACK,
    Color.RED: ManaType.RED,
    Color.GREEN: ManaType.GREEN,
}


class GreatHallOfTheBiblioplex(Land):
    """Great Hall of the Biblioplex — a colorless nonbasic man-land."""

    #: Card-level query surface for the any-color mana's spend restriction
    #: ("spend this mana only to cast an instant or sorcery spell").  Read by
    #: tests / tooling that want to know the land produces restricted mana.
    mana_spend_restriction: str = RESTRICT_INSTANT_SORCERY
    produces_restricted_mana: bool = True

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Great Hall of the Biblioplex")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{T}, Pay 1 life: Add one mana of any color. Spend this mana only "
            "to cast an instant or sorcery spell.\n"
            "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
            'creature with "Whenever you cast an instant or sorcery spell, '
            'this creature gets +1/+0 until end of turn." It\'s still a land.',
        )
        super().__init__(**kwargs)
        # Animation state — a plain (unanimated) land has no power/toughness.
        self._animated: bool = False
        self._anim_base_power: int = _ANIMATED_POWER
        self._anim_base_toughness: int = _ANIMATED_TOUGHNESS
        self.modified_power: int = _ANIMATED_POWER
        self.modified_toughness: int = _ANIMATED_TOUGHNESS
        # Cache the ability surfaces so repeated calls return the same objects
        # (tests identify the any-color ability by identity against the
        # colorless one — ``ab is not colorless``).
        self._mana_abilities: list[ManaAbility] | None = None
        self._activated_abilities: list[ActivatedAbility] | None = None

    # ------------------------------------------------------------------
    # Power / toughness — only meaningful while animated
    # ------------------------------------------------------------------

    @property
    def power(self) -> int | None:
        """Current power while animated; ``None`` for a plain land."""
        if not self._animated:
            return None
        return self.modified_power

    @property
    def toughness(self) -> int | None:
        """Current toughness while animated; ``None`` for a plain land."""
        if not self._animated:
            return None
        return self.modified_toughness

    def _reset_characteristics(self) -> None:
        """Reset card types/keywords; re-seed the animated body if animated.

        The base reset restores ``card_types`` to LAND-only and clears
        keywords; the animation's durable Layer-4 effect re-adds CREATURE and
        the Layer 7b effect re-sets the base body.  We re-seed
        ``modified_power``/``modified_toughness`` here so that Layer 7c pump
        effects (applied after) accumulate on top of the 2/4 base each cycle.
        """
        super()._reset_characteristics()
        if self._animated:
            self.modified_power = self._anim_base_power
            self.modified_toughness = self._anim_base_toughness

    # ------------------------------------------------------------------
    # Controller resolution
    # ------------------------------------------------------------------

    def _resolve_controller(self, game: "GameState") -> Any:
        """Return the player who currently controls this land for *game*.

        Mana / activated abilities add mana, pay life, and animate for "you" —
        the land's controller.  ``self.controller`` is the normal source of
        truth, but when it points at a player from a *different* game (test
        helpers probe abilities against throwaway games), it is resolved
        against *game*: the player whose battlefield holds this land, else the
        active player.  When ``self.controller`` is a genuine member of *game*
        it is returned unchanged, so ordinary play is unaffected.
        """
        controller = self.controller
        if controller is not None and controller in game.players:
            return controller
        for player in game.players:
            if game.get_battlefield(player).contains(self):
                return player
        return game.active_player

    # ------------------------------------------------------------------
    # Mana abilities
    # ------------------------------------------------------------------

    def get_mana_abilities(self) -> list[ManaAbility]:
        if self._mana_abilities is not None:
            return self._mana_abilities

        def colorless_cost(game: "GameState") -> bool:
            if self.is_tapped:
                return False
            self.is_tapped = True
            return True

        def colorless_produce(game: "GameState") -> None:
            # Direct-pool mutation so the resolved controller (not a stale
            # ``self.controller`` left by a probe) receives the mana.
            controller = self._resolve_controller(game)
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        def any_color_cost(game: "GameState") -> bool:
            # {T}, Pay 1 life.
            if self.is_tapped:
                return False
            controller = self._resolve_controller(game)
            if controller is not None:
                controller.life -= 1
            self.is_tapped = True
            return True

        def any_color_produce(game: "GameState") -> None:
            controller = self._resolve_controller(game)
            if controller is None:
                return
            color_options = [
                Color.WHITE,
                Color.BLUE,
                Color.BLACK,
                Color.RED,
                Color.GREEN,
            ]
            chosen = controller.choose(
                color_options,
                "Choose a color of mana to produce with Great Hall of the "
                "Biblioplex",
            )
            mana_type = _COLOR_TO_MANA.get(chosen, chosen)
            # The produced mana may be spent only to cast an instant or sorcery
            # spell (enforced in engine.casting.cast_spell via the pool's
            # restriction record).
            controller.mana_pool.add_restricted(
                mana_type,
                1,
                restriction=RESTRICT_INSTANT_SORCERY,
                source=self,
            )

        colorless = ManaAbility(
            cost=colorless_cost,
            mana_produced=colorless_produce,
            description="{T}: Add {C}.",
        )
        any_color = ManaAbility(
            cost=any_color_cost,
            mana_produced=any_color_produce,
            description=(
                "{T}, Pay 1 life: Add one mana of any color. Spend this mana "
                "only to cast an instant or sorcery spell."
            ),
        )
        # Tag the any-color ability with its spend restriction so a probe can
        # discover it at the ability level too.
        any_color.restriction = RESTRICT_INSTANT_SORCERY  # type: ignore[attr-defined]
        any_color.spend_restriction = RESTRICT_INSTANT_SORCERY  # type: ignore[attr-defined]

        self._mana_abilities = [colorless, any_color]
        return self._mana_abilities

    # ------------------------------------------------------------------
    # Activated ability — {5}: animate
    # ------------------------------------------------------------------

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        if self._activated_abilities is not None:
            return self._activated_abilities

        def animate_cost(game: "GameState") -> bool:
            controller = self._resolve_controller(game)
            if controller is None:
                return False
            if not controller.mana_pool.can_pay(_ANIMATE_COST):
                return False
            return controller.mana_pool.pay(_ANIMATE_COST)

        def animate_effect(game: "GameState") -> None:
            controller = self._resolve_controller(game)
            # "If this land isn't a creature" — guard against re-animation.
            if is_animated(game, self):
                return
            became = animate_land(
                game,
                self,
                _ANIMATED_POWER,
                _ANIMATED_TOUGHNESS,
                subtype=_ANIMATED_SUBTYPE,
                controller=controller,
            )
            if became:
                # Grant the "whenever you cast an instant or sorcery spell,
                # this creature gets +1/+0 until end of turn" trigger.
                register_instant_sorcery_pump(game, self, controller)

        animate = ActivatedAbility(
            cost=animate_cost,
            effect=animate_effect,
            description=(
                "{5}: If this land isn't a creature, it becomes a 2/4 Wizard "
                "creature with \"Whenever you cast an instant or sorcery spell, "
                "this creature gets +1/+0 until end of turn.\" It's still a land."
            ),
        )
        self._activated_abilities = [animate]
        return self._activated_abilities
