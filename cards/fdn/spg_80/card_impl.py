"""Card implementation for Paradise Druid."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import (
    ActivatedAbility,
    Artifact,
    Creature,
    Enchantment,
    Instant,
    ManaAbility,
    Sorcery,
)
from benchmarks.sos.workspace.engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from benchmarks.sos.workspace.engine.types import CardType, Color, HybridManaSymbol, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState

    from cards.registry import CardRegistry

def _tap_cost(game: Any, source: Any) -> bool:
    """Generic tap-cost: check untapped, then tap."""
    if getattr(source, "is_tapped", False):
        return False
    source.is_tapped = True
    return True
def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class ParadiseDruid(Creature):
    """Paradise Druid — {1}{G} — 2/1 — Elf Druid

    Paradise Druid has hexproof as long as it's untapped.
    {T}: Add one mana of any color.

    SPG collector number 80.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Paradise Druid")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", {"Elf", "Druid"})
        kwargs.setdefault(
            "rules_text",
            "Paradise Druid has hexproof as long as it's untapped.\n"
            "{T}: Add one mana of any color.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        """Register a continuous effect for conditional hexproof."""
        source = self

        def _apply_hexproof(g: Any) -> None:
            """Grant hexproof if untapped, remove it if tapped."""
            if not _is_on_battlefield(g, source):
                return
            if not getattr(source, "is_tapped", False):
                source.keywords = source.keywords | Keyword.HEXPROOF
            else:
                source.keywords = Keyword(source.keywords & ~Keyword.HEXPROOF)

        game.effect_manager.add(ContinuousEffect(
            source=source,
            layer=Layer.ABILITY,
            apply=_apply_hexproof,
            duration=DURATION_PERMANENT,
        ))

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return mana abilities for any-color mana production."""
        source = self
        abilities: list[ManaAbility] = []

        # One ability per color for "any color" mana
        for color_name, mana_type in [
            ("W", ManaType.WHITE),
            ("U", ManaType.BLUE),
            ("B", ManaType.BLACK),
            ("R", ManaType.RED),
            ("G", ManaType.GREEN),
        ]:
            def _make_effect(mt: ManaType = mana_type) -> Any:
                def _effect(game: Any) -> None:
                    controller = source.controller
                    if controller is not None:
                        controller.mana_pool.add(mt, 1)
                return _effect

            abilities.append(ManaAbility(
                cost=_tap_cost,
                mana_produced=_make_effect(),
                description=f"{{T}}: Add {{{color_name}}}.",
            ))

        return abilities
