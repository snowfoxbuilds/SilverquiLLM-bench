"""Card implementation for Bushwhack."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Mode, Sorcery
from engine.card_queries import choose_mode, choose_object
from engine.types import CardType, ManaCost, Supertype, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


# Mode indices.
_MODE_SEARCH = 0
_MODE_FIGHT = 1
_MODE_NAMES = ["Search", "Fight"]


class Bushwhack(Sorcery):
    """Bushwhack — {G} — Sorcery.

    Choose one —
    • Search your library for a basic land card, reveal it, put it into your
      hand, then shuffle.
    • Target creature you control fights target creature you don't control.

    FDN collector number 215.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Bushwhack")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Search your library for a basic land card, reveal it, put it "
            "into your hand, then shuffle.\n"
            "• Target creature you control fights target creature you don't "
            "control. (Each deals damage equal to its power to the other.)",
        )
        super().__init__(**kwargs)
        self._chosen_mode_index: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(
                name="Search",
                description="Search your library for a basic land card, reveal "
                "it, put it into your hand, then shuffle.",
            ),
            Mode(
                name="Fight",
                description="Target creature you control fights target creature "
                "you don't control.",
            ),
        ]

    def get_targets(self, game: "GameState") -> list[Any]:
        """Choose the mode. Fight targets two creatures; Search is non-target."""
        controller = self.controller or getattr(self, "owner", None)
        chosen = choose_mode(game, controller, _MODE_NAMES, "Choose one", source_card=self)
        self._chosen_mode_index = _MODE_NAMES.index(chosen)

        if self._chosen_mode_index != _MODE_FIGHT:
            # Search mode chooses its basic land at resolution (non-target).
            return []

        return [
            TargetRequirement(
                filter_fn=self._is_your_creature,
                description="target creature you control",
                zone=Zone.BATTLEFIELD,
            ),
            TargetRequirement(
                filter_fn=self._is_their_creature,
                description="target creature you don't control",
                zone=Zone.BATTLEFIELD,
            ),
        ]

    def _is_your_creature(self, obj: Any) -> bool:
        """A creature the caster controls (shared cast/resolution predicate)."""
        controller = self.controller or getattr(self, "owner", None)
        return (
            CardType.CREATURE in getattr(obj, "card_types", set())
            and getattr(obj, "controller", None) is controller
        )

    def _is_their_creature(self, obj: Any) -> bool:
        """A creature the caster does not control (shared cast/resolution)."""
        controller = self.controller or getattr(self, "owner", None)
        return (
            CardType.CREATURE in getattr(obj, "card_types", set())
            and getattr(obj, "controller", None) is not controller
        )

    def on_resolve(self, game: "GameState") -> None:
        if self._chosen_mode_index == _MODE_SEARCH:
            self._resolve_search(game)
        elif self._chosen_mode_index == _MODE_FIGHT:
            self._resolve_fight(game)

    def _resolve_search(self, game: "GameState") -> None:
        """Search the controller's library for a basic land → hand, then shuffle."""
        controller = self.controller or getattr(self, "owner", None)
        if controller is None:
            return
        library = controller.zones[Zone.LIBRARY]
        basics = [
            c
            for c in library.get_all()
            if CardType.LAND in getattr(c, "card_types", set())
            and Supertype.BASIC in getattr(c, "supertypes", set())
        ]
        if basics:
            # "Search" may fail to find, so the choice is declinable.
            chosen = choose_object(
                game,
                controller,
                basics,
                "Search your library for a basic land card",
                source_card=self,
                optional=True,
            )
            if chosen is not None and library.contains(chosen):
                library.remove(chosen)
                controller.zones[Zone.HAND].add(chosen)
        library.shuffle()

    def _resolve_fight(self, game: "GameState") -> None:
        """The two targeted creatures each deal damage equal to their power."""
        from engine.game import deal_damage

        chosen = getattr(self, "chosen_targets", None) or []
        if len(chosen) < 2:
            return
        yours, theirs = chosen[0], chosen[1]
        # Revalidate the COMPLETE predicate for BOTH targets (rule 608.2b): each
        # must still be on the battlefield and a creature with the correct
        # control relationship. If either changed control or ceased to be a
        # creature, that target is illegal; a fight needs both, so it does
        # nothing (rule 608.2c — the fight cannot happen with an illegal target).
        if not (_on_battlefield(game, yours) and _on_battlefield(game, theirs)):
            return
        if not (self._is_your_creature(yours) and self._is_their_creature(theirs)):
            return
        yours_power = getattr(yours, "power", getattr(yours, "base_power", 0))
        theirs_power = getattr(theirs, "power", getattr(theirs, "base_power", 0))
        deal_damage(game, yours, theirs, yours_power)
        deal_damage(game, theirs, yours, theirs_power)
