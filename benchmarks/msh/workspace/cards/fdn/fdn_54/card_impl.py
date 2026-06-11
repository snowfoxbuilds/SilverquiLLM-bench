"""Card implementation for Abyssal Harvester."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.card_queries import choose_object
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class AbyssalHarvester(Creature):
    """Abyssal Harvester — {1}{B}{B} — 3/2 — Demon Warlock.

    {T}: Exile target creature card from a graveyard that was put there
    this turn. Create a token that's a copy of it, except it's a Nightmare
    in addition to its other types. Then exile all other Nightmare tokens
    you control.

    FDN collector number 54.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abyssal Harvester")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault("subtypes", {"Demon", "Warlock"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{T}: Exile target creature card from a graveyard that was put "
            "there this turn. Create a token that's a copy of it, except it's "
            "a Nightmare in addition to its other types. Then exile all other "
            "Nightmare tokens you control.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self, game: "GameState") -> list:
        """Return the tap ability."""
        from engine.card import ActivatedAbility

        source = self

        def _tap_ability_effect(game: "GameState") -> None:
            from engine.game import create_token, exile

            controller = getattr(source, "controller", None)
            if controller is None:
                return

            # Find creature cards in any graveyard put there this turn
            # ENGINE LIMITATION: no tracking of "put there this turn"
            # Simplified: any creature card in any graveyard
            candidates: list = []
            for player in game.players:
                gy = player.zones[Zone.GRAVEYARD]
                for card in gy.get_all():
                    if CardType.CREATURE in getattr(card, "card_types", set()):
                        candidates.append(card)

            if not candidates:
                return

            chosen = choose_object(game, controller, candidates, "creature card to exile from graveyard", source_card=source)

            if chosen is None:
                return

            # Exile the chosen card
            exile(game, chosen)

            # Create a token that's a copy of the exiled card, except
            # it's a Nightmare in addition to its other types.
            # Copy all copiable values: name, types, subtypes, colors,
            # keywords, P/T, rules text, mana cost.
            token_subtypes = set(getattr(chosen, "subtypes", set())) | {"Nightmare"}
            token_kwargs: dict[str, Any] = {
                "name": getattr(chosen, "name", "Nightmare Token"),
                "subtypes": token_subtypes,
                "base_power": getattr(chosen, "base_power", 0),
                "base_toughness": getattr(chosen, "base_toughness", 0),
            }
            # Copy card types (already Creature from constructor)
            if hasattr(chosen, "keywords") and chosen.keywords:
                token_kwargs["keywords"] = chosen.keywords
            if hasattr(chosen, "colors"):
                token_kwargs["colors"] = chosen.colors
            if hasattr(chosen, "mana_cost") and chosen.mana_cost:
                token_kwargs["mana_cost"] = chosen.mana_cost
            if hasattr(chosen, "rules_text"):
                token_kwargs["rules_text"] = chosen.rules_text
            token = Creature(**token_kwargs)
            create_token(game, controller, token)

            # Exile all other Nightmare tokens you control
            bf = game.get_battlefield(controller)
            to_exile = [
                c for c in bf.get_all()
                if getattr(c, "is_token", False)
                and "Nightmare" in getattr(c, "subtypes", set())
                and c is not token
            ]
            for t in to_exile:
                exile(game, t)

        ability = ActivatedAbility(
            cost=lambda game, src=self: not getattr(src, "is_tapped", False),
            effect=_tap_ability_effect,
            description="{T}: Exile target creature card from a graveyard that was put there this turn. Create a token that's a copy of it, except it's a Nightmare in addition to its other types. Then exile all other Nightmare tokens you control.",
        )
        ability.tap_cost = True
        return [ability]
