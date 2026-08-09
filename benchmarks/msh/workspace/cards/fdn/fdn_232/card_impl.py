"""Card implementation for Scavenging Ooze."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class ScavengingOoze(Creature):
    """Scavenging Ooze — {1}{G} — 2/2 — Ooze

    {G}: Exile target card from a graveyard. If it was a creature card,
    put a +1/+1 counter on this creature and you gain 1 life.

    FDN collector number 232.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scavenging Ooze")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Ooze"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{G}: Exile target card from a graveyard. If it was a creature "
            "card, put a +1/+1 counter on this creature and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # Instant-speed ability: the source must be on the battlefield, and
            # (mirroring "target card from a graveyard") there must be at least
            # one card in some graveyard to choose.
            if controller is None or not _on_battlefield(game, src):
                return False
            return any(
                game.get_graveyard(player).get_all() for player in game.players
            )

        def _cost(game: "GameState", src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{G}"))
            return True

        def _effect(game: "GameState") -> None:
            from engine.game import add_counter, exile, gain_life

            controller = source.controller
            if controller is None:
                return
            # The graveyard card is chosen at resolution via a Player Query —
            # the choice surface answered by Intents / replay-derived Intents.
            cards = [
                card
                for player in game.players
                for card in game.get_graveyard(player).get_all()
            ]
            if not cards:
                return
            chosen = choose_object(
                game,
                controller,
                cards,
                "Choose a card in a graveyard to exile",
                source_card=source,
            )
            if chosen is None:
                return
            is_creature = CardType.CREATURE in getattr(chosen, "card_types", set())
            exile(game, chosen)
            if is_creature and _on_battlefield(game, source):
                add_counter(game, source, "+1/+1", 1)
                gain_life(game, controller, 1)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                can_activate=_can_activate,
                description="{G}: Exile target card from a graveyard. If it "
                "was a creature card, put a +1/+1 counter on this creature "
                "and you gain 1 life.",
            )
        ]
