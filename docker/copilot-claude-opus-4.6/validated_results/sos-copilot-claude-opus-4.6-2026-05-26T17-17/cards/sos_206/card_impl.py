"""Card implementation for Nita, Forum Conciliator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature, Instant, Sorcery
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class NitaForumConciliator(Creature):
    """Nita, Forum Conciliator — {1}{W}{B} — 2/3 — Legendary Creature — Human Advisor.

    Whenever you cast a spell you don't own, put a +1/+1 counter on each creature you control.
    {2}, Sacrifice another creature: Exile target instant or sorcery card from an opponent's
    graveyard. You may cast it this turn, and mana of any type can be spent to cast that spell.
    If that spell would be put into a graveyard, exile it instead. Activate only as a sorcery.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Nita, Forum Conciliator")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Human", "Advisor"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)

    @property
    def legendary(self) -> bool:
        return True

    def on_spell_cast(self, game: "GameState", spell: Any) -> None:
        """Triggered ability: whenever you cast a spell you don't own."""
        controller = self.controller
        # Check if the spell's owner is different from the caster (controller)
        if spell.owner is controller:
            return
        # Put a +1/+1 counter on each creature the controller controls
        bf = game.get_battlefield(controller)
        for card in bf.get_all():
            if isinstance(card, Creature):
                card.plus_one_counters += 1

    def activate_ability(self, game: "GameState", sacrifice: Any = None, target: Any = None) -> None:
        """Activated ability: {2}, Sacrifice another creature: Exile target instant/sorcery."""
        controller = self.controller
        # Cannot sacrifice self
        if sacrifice is self:
            raise ValueError("Cannot sacrifice Nita herself — must sacrifice another creature.")
        # Validate target is instant or sorcery
        if not isinstance(target, (Instant, Sorcery)):
            if not hasattr(target, 'card_types'):
                raise ValueError("Target must be an instant or sorcery card.")
            if CardType.INSTANT not in target.card_types and CardType.SORCERY not in target.card_types:
                raise ValueError("Target must be an instant or sorcery card.")
        # Sacrifice the creature
        bf = game.get_battlefield(controller)
        bf.remove(sacrifice)
        sacrifice.zone = Zone.GRAVEYARD
        # Exile the target from opponent's graveyard
        owner = target.owner
        gy = game.get_graveyard(owner)
        gy.remove(target)
        target.zone = Zone.EXILE
