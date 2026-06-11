"""Card implementation for Professor Dellian Fel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class DellianEmblem:
    """Emblem: Whenever you gain life, target opponent loses that much life."""

    def __init__(self, owner: Any, game: Any) -> None:
        self.owner = owner
        # Monkey-patch gain_life to also drain the opponent
        original_gain_life = owner.gain_life

        emblem_owner = owner

        def _enhanced_gain_life(*args: Any) -> None:
            # Determine game and amount from args
            if len(args) == 2:
                g, amount = args
            elif len(args) == 1:
                amount = args[0]
                g = getattr(emblem_owner, '_game', None)
            else:
                return
            if amount <= 0:
                return
            emblem_owner.life += amount
            # Drain opponent
            if g is not None:
                for p in g.players:
                    if p is not emblem_owner:
                        p.lose_life(amount)
                        break

        owner.gain_life = _enhanced_gain_life


class ProfessorDellianFel(Planeswalker):
    """Professor Dellian Fel — {2}{B}{G} — Legendary Planeswalker — Dellian.

    Loyalty 5.
    +2: You gain 3 life.
    0: You draw a card and lose 1 life.
    −3: Destroy target creature.
    −6: You get an emblem with "Whenever you gain life, target opponent loses that much life."
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Professor Dellian Fel")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}{G}"))
        kwargs.setdefault("starting_loyalty", 5)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", {"Dellian"})
        super().__init__(**kwargs)

    @property
    def is_legendary(self) -> bool:
        return True

    def activate_loyalty_ability(
        self, game: "GameState", ability_index: int, targets: list[Any] | None = None
    ) -> None:
        """Activate the loyalty ability at the given index."""
        controller = self.controller or self.owner

        if ability_index == 0:
            # +2: You gain 3 life
            self.loyalty += 2
            controller.gain_life(game, 3)
        elif ability_index == 1:
            # 0: You draw a card and lose 1 life
            from engine.game import draw_card
            draw_card(game, controller)
            controller.lose_life(1)
        elif ability_index == 2:
            # -3: Destroy target creature
            self.loyalty -= 3
            if targets:
                for target in targets:
                    owner = target.owner
                    bf = game.get_battlefield(owner)
                    gy = game.get_graveyard(owner)
                    if target in bf:
                        bf.remove(target)
                        gy.add(target)
        elif ability_index == 3:
            # -6: Emblem
            self.loyalty -= 6
            if not hasattr(controller, 'emblems'):
                controller.emblems = []
            emblem = DellianEmblem(controller, game)
            controller.emblems.append(emblem)
