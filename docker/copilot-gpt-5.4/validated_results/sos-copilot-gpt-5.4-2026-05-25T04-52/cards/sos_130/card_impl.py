"""Card implementation for Steal the Show."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Mode, Planeswalker, Sorcery
from benchmarks.sos.workspace.engine.casting import CastingError
from benchmarks.sos.workspace.engine.game import deal_damage, discard, draw_card
from benchmarks.sos.workspace.engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class StealTheShow(Sorcery):
    """Steal the Show."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Steal the Show")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        super().__init__(**kwargs)
        self.selected_modes: list[int] = []

    def get_modes(self) -> list[Mode]:
        return [
            Mode(
                name="Loot player",
                description="Target player discards any number of cards, then draws that many cards.",
            ),
            Mode(
                name="Damage permanent",
                description="Steal the Show deals damage equal to the number of instant and sorcery cards in your graveyard to target creature or planeswalker.",
            ),
        ]

    def _normalize_selected_modes(self, raw_choice: Any) -> list[int]:
        if isinstance(raw_choice, bool):
            raise CastingError(f"Cannot cast {self.name!r} — invalid mode selection")
        if isinstance(raw_choice, int):
            chosen_modes = [raw_choice]
        elif isinstance(raw_choice, (list, tuple, set)):
            chosen_modes = list(raw_choice)
        else:
            raise CastingError(f"Cannot cast {self.name!r} — invalid mode selection")

        if not chosen_modes:
            raise CastingError(f"Cannot cast {self.name!r} — at least one mode must be chosen")
        normalized = [int(mode) for mode in chosen_modes]
        if len(normalized) != len(set(normalized)):
            raise CastingError(f"Cannot cast {self.name!r} — duplicate modes chosen")
        if any(mode not in (0, 1) for mode in normalized):
            raise CastingError(f"Cannot cast {self.name!r} — invalid mode chosen")
        if len(normalized) > 2:
            raise CastingError(f"Cannot cast {self.name!r} — too many modes chosen")
        return normalized

    def _ensure_selected_modes(self) -> None:
        if self.selected_modes:
            self.selected_modes = self._normalize_selected_modes(self.selected_modes)
            return
        controller = self.controller
        if controller is None:
            return
        mode_choice = controller.choose([[0], [1], [0, 1]], "choose one or both modes")
        self.selected_modes = self._normalize_selected_modes(mode_choice)

    def get_targets(self, game: GameState) -> list[TargetRequirement]:  # noqa: ARG002
        self._ensure_selected_modes()
        targets: list[TargetRequirement] = []
        if 0 in self.selected_modes:
            targets.append(
                TargetRequirement(
                    filter_fn=lambda obj: hasattr(obj, "life") and hasattr(obj, "zones"),
                    description="target player",
                    zone=Zone.BATTLEFIELD,
                )
            )
        if 1 in self.selected_modes:
            targets.append(
                TargetRequirement(
                    filter_fn=lambda obj: isinstance(obj, (Creature, Planeswalker)),
                    description="target creature or planeswalker",
                    zone=Zone.BATTLEFIELD,
                )
            )
        return targets

    def _resolve_discard_draw_mode(self, game: GameState, target_player: Any) -> None:
        if not hasattr(target_player, "zones"):
            return
        discarded_count = 0
        while True:
            hand = game.get_hand(target_player).get_all()
            if not hand:
                break
            if not target_player.choose_yes_no("Discard a card for Steal the Show?"):
                break
            chosen = target_player.choose_card(hand, "card to discard")
            if chosen not in hand:
                break
            discard(game, target_player, chosen)
            discarded_count += 1
        for _ in range(discarded_count):
            draw_card(game, target_player)

    def _resolve_damage_mode(self, game: GameState, target: Any) -> None:
        controller = self.controller
        if controller is None or not isinstance(target, CardImpl) or not target.is_on_battlefield(game):
            return
        damage = sum(
            1
            for card in game.get_graveyard(controller).get_all()
            if CardType.INSTANT in getattr(card, "card_types", set())
            or CardType.SORCERY in getattr(card, "card_types", set())
        )
        deal_damage(game, self, target, damage)

    def on_resolve(self, game: GameState) -> None:
        targets = list(getattr(self, "chosen_targets", []))
        target_index = 0
        for mode in self.selected_modes:
            if mode == 0:
                target_player = targets[target_index] if target_index < len(targets) else None
                target_index += 1
                self._resolve_discard_draw_mode(game, target_player)
            elif mode == 1:
                target = targets[target_index] if target_index < len(targets) else None
                target_index += 1
                if isinstance(target, (Creature, Planeswalker)):
                    self._resolve_damage_mode(game, target)
