"""Card implementation for Apothecary Stomper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Mode
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class ApothecaryStomperAbility1:
    text = "Vigilance (Attacking doesn't cause this creature to tap.)"


class ApothecaryStomperAbility2:
    text = 'When this creature enters, choose one —'


class ApothecaryStomperAbility3:
    text = '• Put two +1/+1 counters on target creature you control.'


class ApothecaryStomperAbility4:
    text = '• You gain 4 life.'


# endregion Printed abilities


class ApothecaryStomper(Creature):
    """Apothecary Stomper — {4}{G}{G} — 4/4 — Elephant — Vigilance.

    Vigilance
    When this creature enters, choose one —
    • Put two +1/+1 counters on target creature you control.
    • You gain 4 life.

    FDN collector number 99.

    Modal enters trigger: the mode is chosen as the trigger goes on the stack
    (``_enters_targets``, rule 603.3d) and kept for that occurrence; mode 0
    then chooses a "target creature you control", mode 1 (gain life) is
    non-targeted. Choosing mode 0 with no creature to target is rejected and
    the mode asked again (rule 700.2a). The effect resolves once the Stomper
    is on the battlefield.
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
                printed=ApothecaryStomperAbility3,
            ),
            Mode(name="Life", description="You gain 4 life.", printed=ApothecaryStomperAbility4),
        ]

    def _enters_targets(self, game: "GameState", controller: Any) -> list[Any]:
        """Choose the mode as the trigger goes on the stack; only the counters mode targets."""
        from engine.card_queries import choose_mode

        modes = self.get_modes()
        chosen_name = choose_mode(
            game,
            controller,
            [m.name for m in modes],
            "Choose one",
            source_card=self,
            printed=[m.printed for m in modes],
        )
        self.chosen_mode = next(
            i for i, m in enumerate(modes) if m.name == chosen_name
        )

        if self.chosen_mode == 0:
            return [
                TargetRequirement(
                    filter_fn=lambda obj, _c=controller: self._is_creature_you_control(obj, _c),
                    description="target creature you control",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        return []

    @staticmethod
    def _is_creature_you_control(obj: Any, controller: Any) -> bool:
        """Legal target: a creature currently controlled by the ability's controller."""
        return (
            CardType.CREATURE in getattr(obj, "card_types", set())
            and getattr(obj, "controller", None) is controller
        )

    def register_triggers(self, game: "GameState") -> None:
        """The enters ability is a triggered ability that uses the stack."""
        from engine.triggers import register_enters_trigger

        # The mode is chosen with the targets, so each occurrence keeps its own.
        register_enters_trigger(
            game,
            self,
            ApothecaryStomperAbility2,
            self._enters,
            targets=self._enters_targets,
            remember=lambda game, controller: self.chosen_mode,
            modal=True,
        )

    def _enters(self, game: "GameState", targets: list[Any], controller: Any, remembered: int | None) -> None:
        mode = remembered
        if mode is None or controller is None:
            return

        if mode == 0:
            from engine.game import add_counter

            chosen = targets
            target = chosen[0] if chosen else None
            if target is None:
                return
            # Revalidate the COMPLETE target predicate at resolution (608.2b):
            # still a creature you control, still on the battlefield — not
            # merely still present. If it lost creature-ness or changed
            # control, the counters are not placed.
            on_bf = game.get_battlefield(controller).contains(target)
            if not on_bf or not self._is_creature_you_control(target, controller):
                return
            add_counter(game, target, "+1/+1", 2)
        elif mode == 1:
            from engine.game import gain_life

            gain_life(game, controller, 4)
