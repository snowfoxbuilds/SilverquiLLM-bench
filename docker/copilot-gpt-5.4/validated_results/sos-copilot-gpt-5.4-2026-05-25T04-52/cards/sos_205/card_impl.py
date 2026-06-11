"""Card implementation for Moment of Reckoning."""

from __future__ import annotations

from itertools import product
from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Mode, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.game import destroy
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


_NONLAND_PERMANENT_TYPES = {
    CardType.CREATURE,
    CardType.ENCHANTMENT,
    CardType.ARTIFACT,
    CardType.PLANESWALKER,
}


def _is_nonland_permanent(card: Any) -> bool:
    card_types = getattr(card, "card_types", set())
    if CardType.LAND in card_types:
        return False
    return bool(card_types & _NONLAND_PERMANENT_TYPES)


class MomentOfReckoning(Sorcery):
    """Moment of Reckoning."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Moment of Reckoning")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{W}{W}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Choose up to four. You may choose the same mode more than once.\n"
            "• Destroy target nonland permanent.\n"
            "• Return target nonland permanent card from your graveyard to the battlefield.\n"
        )
        super().__init__(**kwargs)
        self.selected_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(
                name="Destroy",
                description="Destroy target nonland permanent.",
            ),
            Mode(
                name="Return",
                description="Return target nonland permanent card from your graveyard to the battlefield.",
            ),
        ]

    def _normalize_selected_modes(self, raw_choice: Any) -> list[int]:
        if raw_choice is None:
            return []
        if isinstance(raw_choice, bool):
            raise CastingError(f"Cannot cast {self.name!r} — invalid mode selection")
        if isinstance(raw_choice, int):
            selected_modes = [raw_choice]
        elif isinstance(raw_choice, (list, tuple)):
            selected_modes = list(raw_choice)
        else:
            raise CastingError(f"Cannot cast {self.name!r} — invalid mode selection")

        normalized = [int(mode) for mode in selected_modes]
        if len(normalized) > 4:
            raise CastingError(f"Cannot cast {self.name!r} — too many modes chosen")
        if any(mode not in (0, 1) for mode in normalized):
            raise CastingError(f"Cannot cast {self.name!r} — invalid mode chosen")
        return normalized

    def _ensure_selected_modes(self) -> None:
        if self.selected_modes is not None:
            self.selected_modes = self._normalize_selected_modes(self.selected_modes)
            return
        controller = self.controller
        if controller is None:
            self.selected_modes = []
            return
        mode_options = [
            list(choice)
            for count in range(5)
            for choice in product((0, 1), repeat=count)
        ]
        self.selected_modes = self._normalize_selected_modes(
            controller.choose(mode_options, "choose up to four modes in order")
        )

    def get_targets(self, game: GameState) -> list[TargetRequirement]:
        controller = self.controller
        self._ensure_selected_modes()
        requirements: list[TargetRequirement] = []
        for selected_mode in self.selected_modes or []:
            if selected_mode == 0:
                requirements.append(
                    TargetRequirement(
                        filter_fn=_is_nonland_permanent,
                        description="target nonland permanent",
                        zone=Zone.BATTLEFIELD,
                    )
                )
                continue

            requirements.append(
                TargetRequirement(
                    filter_fn=lambda card, current_controller=controller: (
                        _is_nonland_permanent(card)
                        and getattr(card, "owner", None) is current_controller
                    ),
                    description="target nonland permanent card in your graveyard",
                    zone=Zone.GRAVEYARD,
                )
            )
        return requirements

    def on_resolve(self, game: GameState) -> None:
        controller = self.controller
        if controller is None:
            return

        self._ensure_selected_modes()
        chosen_targets = list(getattr(self, "chosen_targets", []))
        for index, selected_mode in enumerate(self.selected_modes or []):
            if index >= len(chosen_targets):
                break
            target = chosen_targets[index]
            if selected_mode == 0:
                if any(game.get_battlefield(player).contains(target) for player in game.players) and _is_nonland_permanent(target):
                    destroy(game, target)
                continue

            if not _is_nonland_permanent(target):
                continue
            if not game.get_graveyard(controller).contains(target):
                continue
            target.controller = controller
            move_to_zone(game, target, Zone.GRAVEYARD, Zone.BATTLEFIELD)
