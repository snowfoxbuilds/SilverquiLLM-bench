"""Card implementation for Together as One.

Together as One — {6} — Sorcery (Rare)
Converge — Target player draws X cards, Together as One deals X damage
to any target, and you gain X life, where X is the number of colors of
mana spent to cast this spell.

Converge is an ability word (flavour text prefix), NOT a keyword.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_player(obj: Any) -> bool:
    """Filter function: target must be a player (has life attribute and zones)."""
    return hasattr(obj, "life") and hasattr(obj, "zones")


def _is_any_target(obj: Any) -> bool:
    """Filter function: target must be a creature, planeswalker, or player.

    'Any target' in MTG means a creature, planeswalker, or player.
    """
    # Player
    if hasattr(obj, "life") and hasattr(obj, "zones"):
        return True
    # Creature or planeswalker (has card_types)
    card_types = getattr(obj, "card_types", set())
    if CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types:
        return True
    return False


class TogetherAsOne(Sorcery):
    """Together as One — {6} — Sorcery.

    Converge — Target player draws X cards, Together as One deals X damage
    to any target, and you gain X life, where X is the number of colors of
    mana spent to cast this spell.

    Implementation notes:
    - colors_spent is recorded at cast time on the card by the casting engine.
    - On resolve, X = len(colors_spent).
    - Multi-effect fizzle: if ALL targets are illegal at resolution, the
      spell is countered (no effects at all). If at least one target is
      still legal, resolve legal effects + life gain.
    - Converge is an ability word, NOT a keyword — no Keyword.CONVERGE.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Together as One")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault(
            "rules_text",
            "Converge \u2014 Target player draws X cards, Together as One deals "
            "X damage to any target, and you gain X life, where X is the number "
            "of colors of mana spent to cast this spell.",
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        """Return two TargetRequirements: target player, and any target."""
        return [
            TargetRequirement(
                filter_fn=_is_player,
                description="target player",
                zone=Zone.BATTLEFIELD,  # not used for players
            ),
            TargetRequirement(
                filter_fn=_is_any_target,
                description="any target (creature, planeswalker, or player)",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        """Resolve Together as One.

        X = number of colors of mana spent to cast.
        - Target player draws X cards.
        - Deal X damage to any target (creature/planeswalker/player).
        - Controller gains X life.

        Multi-effect fizzle rules:
        - If ALL targets are illegal at resolution, the spell is countered
          on resolution — no effects happen (including life gain).
        - If at least one target is still legal, resolve legal parts and
          the untargeted life gain effect.
        """
        from engine.game import deal_damage, draw_card

        # Determine X from colors_spent (set by casting engine)
        colors_spent = getattr(self, "colors_spent", None)
        if colors_spent is None:
            x = 0
        elif isinstance(colors_spent, int):
            x = colors_spent
        else:
            # It's a list of Color values
            x = len(colors_spent)

        if x <= 0:
            return

        # Retrieve targets (set by _resolve_spell or test setup)
        targets = getattr(self, "chosen_targets", None) or []
        controller = self.controller

        # Target 0: target player (draws X)
        draw_target = targets[0] if len(targets) > 0 else None
        # Target 1: any target (damage X)
        damage_target = targets[1] if len(targets) > 1 else None

        # Validate each target
        draw_legal = draw_target is not None and self._is_valid_player(draw_target, game)
        damage_legal = damage_target is not None and self._is_valid_target(damage_target, game)

        # If ALL targets are illegal, the spell is countered — no effects.
        if not draw_legal and not damage_legal:
            return

        # At least one target is legal — resolve legal parts + life gain.

        # Effect 1: Target player draws X cards
        if draw_legal:
            for _ in range(x):
                draw_card(game, draw_target)

        # Effect 2: Deal X damage to any target
        if damage_legal:
            deal_damage(game, self, damage_target, x)

        # Effect 3: Controller gains X life (untargeted — resolves if spell resolves)
        if controller is not None:
            controller.life += x

    # ------------------------------------------------------------------
    # Target validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_player(target: Any, game: GameState) -> bool:
        """Check if target is still a valid player in the game."""
        if hasattr(target, "life"):
            return target in game.players
        return False

    @staticmethod
    def _is_valid_target(target: Any, game: GameState) -> bool:
        """Check if target is still valid (player or permanent on battlefield)."""
        # Player target
        if hasattr(target, "life") and target in game.players:
            return True
        # Creature/planeswalker on battlefield
        for player in game.players:
            bf = player.zones[Zone.BATTLEFIELD]
            if bf.contains(target):
                return True
        return False
