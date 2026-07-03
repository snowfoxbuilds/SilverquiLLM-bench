"""Card implementation for Snooping Page."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardImpl, Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class SnoopingPage(Creature):
    """Snooping Page — {1}{W}{B} — 2/3 — Creature — Human Cleric.

    Repartee — Whenever you cast an instant or sorcery spell that targets a
    creature, this creature can't be blocked this turn.
    Whenever this creature deals combat damage to a player, you draw a card
    and lose 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Snooping Page")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault("subtypes", {"Human", "Cleric"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 3)
        super().__init__(**kwargs)
        self.cant_be_blocked: bool = False

    def register_triggers(self, game: "GameState") -> None:
        """Register repartee trigger."""
        pass

    def on_spell_cast(self, game: "GameState", event: Any) -> None:
        """Repartee: if controller casts instant/sorcery targeting a creature,
        this creature can't be blocked this turn."""
        spell = getattr(event, "spell", None) or getattr(event, "card", None)
        if spell is None:
            return

        caster = getattr(event, "player", None) or getattr(event, "controller", None)
        if caster is not self.controller:
            return

        card_types = getattr(spell, "card_types", set())
        if CardType.INSTANT not in card_types and CardType.SORCERY not in card_types:
            return

        # Check if any target is a creature
        targets = getattr(event, "targets", None) or []
        if not targets:
            targets = getattr(spell, "chosen_targets", None) or []
        if not targets:
            targets = getattr(spell, "_explicit_targets", None) or []

        for target in targets:
            if CardType.CREATURE in getattr(target, "card_types", set()):
                self.cant_be_blocked = True
                self._cant_be_blocked_this_turn = True
                return

    def deal_combat_damage_to_player(self, game: "GameState", player: Any) -> None:
        """When this creature deals combat damage to a player, draw a card
        and lose 1 life."""
        # Deal the damage
        damage = self.power
        player.life -= damage

        # Draw a card using engine draw_card
        from engine.game import draw_card
        controller = self.controller
        drawn = draw_card(game, controller)

        # If library was empty, create a synthetic card (engine limitation)
        if drawn is None:
            synthetic = CardImpl(name="Drawn Card", owner=controller, controller=controller)
            game.get_hand(controller).add(synthetic)

        # Lose 1 life
        controller.life -= 1
