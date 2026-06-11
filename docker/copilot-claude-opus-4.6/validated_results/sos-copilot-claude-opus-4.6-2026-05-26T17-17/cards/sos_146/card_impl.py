"""Card implementation for Emil, Vastlands Roamer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState


class EmilVastlandsRoamer(Creature):
    """Emil, Vastlands Roamer — {2}{G} — Legendary Creature — Elf Druid — 3/3.

    Creatures you control with +1/+1 counters on them have trample.
    {4}{G}, {T}: Create a 0/0 green and blue Fractal creature token.
    Put X +1/+1 counters on it, where X is the number of differently named
    lands you control.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emil, Vastlands Roamer")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{G}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        super().__init__(**kwargs)
        self.activated_abilities: list[ActivatedAbility] = [
            ActivatedAbility(
                cost=lambda game: None,
                effect=self._create_fractal,
                description="{4}{G}, {T}: Create a Fractal token with X +1/+1 counters.",
            )
        ]
        self._bf_zone = None

    def _apply_trample_to(self, card: Any) -> None:
        """Grant trample to a creature if it has +1/+1 counters."""
        card_types = getattr(card, "card_types", set())
        if CardType.CREATURE in card_types:
            counters = getattr(card, "plus_one_counters", 0)
            if counters > 0:
                card.keywords = card.keywords | Keyword.TRAMPLE

    def _on_bf_add(self, obj: Any) -> None:
        """Callback for when something is added to our battlefield."""
        self._apply_trample_to(obj)

    def on_zone_enter(self, zone: Any) -> None:
        """Called when Emil enters a zone. Register trample granting."""
        self._bf_zone = zone
        zone._on_add_callbacks.append(self._on_bf_add)
        # Apply trample to all existing creatures with counters
        for card in zone:
            self._apply_trample_to(card)

    def _create_fractal(self, game: "GameState") -> None:
        """Create a 0/0 Fractal token with X +1/+1 counters."""
        controller = self.controller
        if controller is None:
            return

        # Count differently named lands
        bf = game.get_battlefield(controller)
        land_names: set[str] = set()
        for card in bf:
            card_types = getattr(card, "card_types", set())
            if CardType.LAND in card_types:
                land_names.add(card.name)

        x = len(land_names)

        fractal = Creature(
            name="Fractal",
            owner=controller,
            controller=controller,
            base_power=0,
            base_toughness=0,
        )
        fractal.card_types = {CardType.CREATURE}
        fractal.subtypes = {"Fractal"}
        fractal.is_token = True
        fractal.plus_one_counters = x

        bf.add(fractal)
