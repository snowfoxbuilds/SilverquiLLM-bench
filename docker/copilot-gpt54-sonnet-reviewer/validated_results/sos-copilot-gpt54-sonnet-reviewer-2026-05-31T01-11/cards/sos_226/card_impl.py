"""Card implementation for Silverquill, the Disputant."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.game import sacrifice
from engine.stack import StackObject, copy_spell
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from engine.stack import StackObject as StackObjectType


class SilverquillTheDisputant(Creature):
    """Silverquill, the Disputant."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Silverquill, the Disputant")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Elder", "Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING | Keyword.VIGILANCE)
        kwargs.setdefault(
            "rules_text",
            "Flying, vigilance\n"
            "Each instant and sorcery spell you cast has casualty 1.",
        )
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)

    def on_controller_cast_spell(
        self,
        game: GameState,
        player: Player,
        spell: Any,
        stack_obj: StackObjectType,
    ) -> None:
        """Grant casualty 1 to the controller's instants and sorceries."""
        if getattr(self, "controller", None) is not player:
            return

        card_types = getattr(spell, "card_types", set())
        if not card_types & {CardType.INSTANT, CardType.SORCERY}:
            return

        battlefield = game.get_battlefield(player)
        candidates = [
            permanent
            for permanent in battlefield.get_all()
            if CardType.CREATURE in getattr(permanent, "card_types", set())
            and getattr(permanent, "power", 0) >= 1
        ]
        if not candidates:
            return

        if not player.choose_yes_no(f"Sacrifice a creature for casualty 1 on {spell.name}?"):
            return

        chosen = player.choose_card(candidates, "Choose a creature to sacrifice for casualty 1")
        if chosen not in candidates or not battlefield.contains(chosen):
            return
        if getattr(chosen, "power", 0) < 1:
            return

        sacrifice(game, player, chosen)

        def _resolve_casualty_copy(g: GameState) -> None:
            if stack_obj not in g.stack._items:
                return

            new_targets: list[Any] | None = None
            if stack_obj.targets and player.choose_yes_no(
                f"Choose new targets for copy of {spell.name}?"
            ):
                requirements = getattr(spell, "get_targets", lambda _game: [])(g)
                new_targets = list(stack_obj.targets)
                for index, requirement in enumerate(requirements):
                    legal = []
                    for candidate_player in g.players:
                        zone = candidate_player.zones[getattr(requirement, "zone")]
                        for obj in zone.get_all():
                            if requirement.filter_fn(obj):
                                legal.append(obj)
                        if requirement.filter_fn(candidate_player):
                            legal.append(candidate_player)
                    if legal:
                        new_targets[index] = player.choose_target(legal, requirement)

            g.stack.push(copy_spell(g, stack_obj, player, new_targets))

        gso = StackObject(
            source=spell,
            controller=player,
            on_resolve=_resolve_casualty_copy,
        )
        game.stack.push(gso)
