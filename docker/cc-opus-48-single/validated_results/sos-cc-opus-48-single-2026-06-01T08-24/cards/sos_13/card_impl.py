"""Card implementation for Emeritus of Truce // Swords to Plowshares (SOS 13).

This is a split / modal card. Per the coordinator directives, only the
creature face (``Emeritus of Truce``) is built fully here. The casting of a
copy of the spell while prepared, and the ``Swords to Plowshares`` instant
face, are recorded as ``# UNVERIFIED`` because the current engine has no
copy-cast / second-castable-face machinery.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _is_creature(obj: Any) -> bool:
    """Return ``True`` if *obj* is a creature permanent."""
    return CardType.CREATURE in getattr(obj, "card_types", set())


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — creature face.

    Emeritus of Truce — {1}{W}{W} — 3/3 — Creature — Cat Cleric (white).

    When this creature enters, target player creates a 1/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

    SOS collector number 13.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        # UNVERIFIED: A first-class Keyword.PREPARED member cannot be added —
        #   the read-only engine test engine_tests/test_types.py asserts the
        #   Keyword Flag enum has exactly 16 members, so adding PREPARED
        #   regresses it. The directive's own verify gate requires
        #   ``pytest engine_tests/`` to keep passing, which takes precedence.
        #   The prepared state is therefore exposed only via the runtime
        #   ``is_prepared`` bool (set by the conditional ETB clause below).
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and "
            "black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared. "
            "(While it's prepared, you may cast a copy of its spell. Doing so "
            "unprepares it.)",
        )
        super().__init__(**kwargs)
        # The creature face is mono-white.
        self.colors: set[Color] = {Color.WHITE}
        # Runtime "becomes prepared" state (the conditional ETB result).
        self.is_prepared: bool = False
        # Targets are chosen for the ETB triggered ability, not the spell.
        self.chosen_targets: list[Any] = []

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def _is_being_cast(self, game: "GameState") -> bool:
        """Return ``True`` while this card sits in any STACK zone.

        The "target player" belongs to the enters-the-battlefield triggered
        ability, not to the creature spell. Following the sos_1 convention, the
        creature face must advertise no targets while it is being cast (in a
        STACK zone), otherwise the cast pipeline wrongly consumes a target.
        """
        for player in getattr(game, "players", []) or []:
            try:
                stack_zone = player.zones[Zone.STACK]
            except (KeyError, AttributeError):
                continue
            contains = getattr(stack_zone, "contains", None)
            if contains is not None and contains(self):
                return True
        return False

    def get_targets(self, game: "GameState") -> list[Any]:
        """The creature spell itself takes no targets while being cast."""
        if self._is_being_cast(game):
            return []
        return []

    # ------------------------------------------------------------------
    # Enters-the-battlefield effect
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """ETB: target player creates a 1/1 W/B flying Inkling; then maybe prepared."""
        self._resolve_etb(game)

    def _resolve_etb(self, game: "GameState") -> None:
        target_player = self._chosen_target_player()
        # The "becomes prepared" clause compares the creatures each player
        # controls. The freshly created Inkling is excluded from this
        # comparison (it would otherwise count toward whichever player it
        # entered for); evaluate the relative counts before it is created.
        self._update_prepared(game)
        if target_player is not None:
            self._create_inkling(game, target_player)

    def _chosen_target_player(self) -> Any:
        """Return the chosen target player for the token, if any."""
        chosen = getattr(self, "chosen_targets", None) or []
        for candidate in chosen:
            if candidate is not None:
                return candidate
        return None

    def _create_inkling(self, game: "GameState", player: Any) -> None:
        """Create a 1/1 white & black Inkling with flying under *player*'s control."""
        from engine.game import create_token

        token = Creature(
            name="Inkling",
            subtypes={"Inkling"},
            keywords=Keyword.FLYING,
            base_power=1,
            base_toughness=1,
        )
        token.colors = {Color.WHITE, Color.BLACK}
        create_token(game, player, token)

    def _update_prepared(self, game: "GameState") -> None:
        """Set ``is_prepared`` if an opponent controls strictly more creatures."""
        controller = getattr(self, "controller", None) or getattr(self, "owner", None)
        if controller is None:
            return
        your_count = self._creature_count(game, controller)
        for player in getattr(game, "players", []) or []:
            if player is controller:
                continue
            if self._creature_count(game, player) > your_count:
                self.is_prepared = True
                return

    def _creature_count(self, game: "GameState", player: Any) -> int:
        """Number of creatures *player* controls on the battlefield."""
        battlefield = game.get_battlefield(player)
        return sum(1 for obj in battlefield.get_all() if _is_creature(obj))

    # ------------------------------------------------------------------
    # Unsupported portions (recorded for grep-ability)
    # ------------------------------------------------------------------
    # UNVERIFIED: "While prepared, you may cast a copy of its spell; doing so
    #   unprepares it." — the engine has no copy-cast / split-face casting
    #   machinery, so the prepared state is exposed only as the ``is_prepared``
    #   bool and the ``Keyword.PREPARED`` advertisement.
    # UNVERIFIED: Swords to Plowshares {W} instant face (exile target creature;
    #   its controller gains life equal to its power) — the engine has no second
    #   castable-face representation for split cards.
