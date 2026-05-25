"""Card implementation for Gorehorn Raider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.types import ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState


class GorehornRaider(Creature):
    """Gorehorn Raider — {4}{R} — 4/4 — Minotaur Pirate.

    Raid — When this creature enters, if you attacked this turn, this
    creature deals 2 damage to any target.

    FDN collector number 89.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gorehorn Raider")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}"))
        kwargs.setdefault("subtypes", {"Minotaur", "Pirate"})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Raid — When this creature enters, if you attacked this turn, "
            "this creature deals 2 damage to any target.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: Raid — deal 2 damage to any target if attacked this turn."""
        from benchmarks.sos.workspace.engine.game import deal_damage

        controller = self.controller
        if controller is None:
            return

        attacked_this_turn = getattr(game, "attacked_this_turn", False)
        if not attacked_this_turn:
            combat = getattr(game, "combat", None)
            if combat is not None:
                attackers = getattr(combat, "attackers", [])
                for attacker in attackers:
                    if getattr(attacker, "controller", None) is controller:
                        attacked_this_turn = True
                        break
        if not attacked_this_turn:
            attacked_this_turn = getattr(controller, "attacked_this_turn", False)

        if not attacked_this_turn:
            return

        # Any target: creatures on battlefield + players
        from benchmarks.sos.workspace.engine.types import CardType
        targets: list = list(game.players)
        for player in game.players:
            bf = game.get_battlefield(player)
            for obj in bf.get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)

        if not targets:
            return

        try:
            chosen = controller.choose_card(targets, "target for 2 damage")
        except Exception:
            chosen = targets[0]

        if chosen is not None:
            deal_damage(game, self, chosen, 2)
