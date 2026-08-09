"""Card implementation for Apothecary Stomper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Mode
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class ApothecaryStomper(Creature):
    """Apothecary Stomper — {4}{G}{G} — 4/4 — Elephant — Vigilance.

    Vigilance
    When this creature enters, choose one —
    • Put two +1/+1 counters on target creature you control.
    • You gain 4 life.

    FDN collector number 99.

    Modal ETB (Pattern 5 + Pattern 1): the mode is chosen at cast in
    ``get_targets``; mode 0 returns a "target creature you control" requirement
    and mode 1 (gain life) is non-targeted. The effect resolves in
    ``on_resolve`` before the Stomper arrives.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Apothecary Stomper")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{G}{G}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", {"Elephant"})
        kwargs.setdefault("keywords", Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Vigilance\nWhen this creature enters, choose one —\n"
            "• Put two +1/+1 counters on target creature you control.\n"
            "• You gain 4 life.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(
                name="Counters",
                description="Put two +1/+1 counters on target creature you control.",
            ),
            Mode(name="Life", description="You gain 4 life."),
        ]

    def get_targets(self, game: "GameState") -> list[Any]:
        """Choose the mode; return a target requirement only for mode 0."""
        from engine.card_queries import choose_mode

        controller = self.controller or getattr(self, "owner", None)
        modes = self.get_modes()
        chosen_name = choose_mode(
            game,
            controller,
            [m.name for m in modes],
            "Choose one",
            source_card=self,
        )
        self.chosen_mode = next(
            i for i, m in enumerate(modes) if m.name == chosen_name
        )

        if self.chosen_mode == 0:
            return [
                TargetRequirement(
                    filter_fn=self._is_creature_you_control,
                    description="target creature you control",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        return []

    def _is_creature_you_control(self, obj: Any) -> bool:
        """Legal target: a creature currently controlled by the caster."""
        controller = self.controller or getattr(self, "owner", None)
        return (
            CardType.CREATURE in getattr(obj, "card_types", set())
            and getattr(obj, "controller", None) is controller
        )

    def on_resolve(self, game: "GameState") -> None:
        mode = self.chosen_mode
        controller = self.controller or getattr(self, "owner", None)
        if mode is None or controller is None:
            return

        if mode == 0:
            from engine.game import add_counter

            chosen = getattr(self, "chosen_targets", None) or []
            target = chosen[0] if chosen else None
            if target is None:
                return
            # Revalidate the COMPLETE target predicate at resolution (608.2b):
            # still a creature you control, still on the battlefield — not
            # merely still present. If it lost creature-ness or changed
            # control, the counters are not placed.
            on_bf = game.get_battlefield(controller).contains(target)
            if not on_bf or not self._is_creature_you_control(target):
                return
            add_counter(game, target, "+1/+1", 2)
        elif mode == 1:
            from engine.game import gain_life

            gain_life(game, controller, 4)
