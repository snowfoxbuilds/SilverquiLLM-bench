"""Card implementation for Improvisation Capstone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import Color, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _mana_value(card: Any) -> int:
    """Return *card*'s mana value (converted mana cost).

    Lands and other zero-cost cards have mana value 0.
    """
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return mana_cost.cmc


def _is_castable_spell(card: Any) -> bool:
    """Return ``True`` if *card* is a spell that can be cast (not a land)."""
    from engine.paradigm import is_castable_spell

    return is_castable_spell(card)


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater.  You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell.  After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

    SOS collector number 120.
    """

    #: The printed paradigm keyword label (Paradigm is NOT an evergreen
    #: ``engine.types.Keyword`` enum member — that enum is frozen at 16
    #: members — so it is recorded here as a printed-keyword label).
    PARADIGM_LABEL = "Paradigm"

    #: Total mana value the exile process accumulates to before stopping.
    EXILE_THRESHOLD = 4

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Improvisation Capstone")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{R}{R}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        kwargs.setdefault(
            "rules_text",
            "Exile cards from the top of your library until you exile cards "
            "with total mana value 4 or greater. You may cast any number of "
            "spells from among them without paying their mana costs.\n"
            "Paradigm (Then exile this spell. After you first resolve a spell "
            "with this name, you may cast a copy of it from exile without "
            "paying its mana cost at the beginning of each of your first main "
            "phases.)",
        )
        super().__init__(**kwargs)
        # Red is given explicitly so colour is correct even off the stack
        # (the cost pips are also red, but being explicit keeps colour stable
        # for copies and for cards stripped of their cost).
        self.colors: list[Color] = [Color.RED]
        # Printed-keyword label surface — Paradigm is a printed keyword, not an
        # evergreen ``Keyword`` enum member.
        self.printed_keywords: list[str] = [self.PARADIGM_LABEL]

    # ------------------------------------------------------------------
    # Paradigm copy factory
    # ------------------------------------------------------------------

    def make_paradigm_copy(self) -> "ImprovisationCapstone":
        """Return a fresh same-named copy of this spell for paradigm.

        The copy is a brand-new :class:`ImprovisationCapstone` (so it can be
        placed in exile and cast for free at the beginning of each of the
        controller's first main phases).  Owner/controller are inherited from
        this card so the copy belongs to the right player.
        """
        copy = ImprovisationCapstone(owner=self.owner, controller=self.controller)
        copy.is_paradigm_copy = True
        return copy

    # ------------------------------------------------------------------
    # Main resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Improvisation Capstone.

        1. Exile cards from the top of the controller's library until the total
           exiled mana value reaches 4 or greater (or the library is empty).
        2. The controller may cast any number of those exiled spells for free.
        3. "Then exile this spell." — register a stack->exile redirect so the
           Capstone is exiled rather than put into the graveyard.
        4. On first resolution, wire the recurring paradigm copy ability.
        """
        controller = self.controller
        if controller is None:
            controller = game.active_player
        if controller is None:
            return

        exiled = self._exile_from_library(game, controller)
        self._offer_free_casts(game, controller, exiled)
        self._exile_this_spell(game)
        self._wire_paradigm(game, controller)

    # ------------------------------------------------------------------
    # Step 1 — exile from library until total mana value >= 4
    # ------------------------------------------------------------------

    def _exile_from_library(self, game: "GameState", controller: Any) -> list[Any]:
        """Exile from the top of *controller*'s library until total MV >= 4.

        Returns the list of cards exiled (top-of-library order).  Mana-value-0
        cards do not stop the process; an empty (or too-small) library simply
        stops once it runs dry — no crash / infinite loop.
        """
        library = controller.zones[Zone.LIBRARY]
        exile = controller.zones[Zone.EXILE]
        exiled: list[Any] = []
        total = 0

        while total < self.EXILE_THRESHOLD:
            # Top of the library is the last element of the internal list.
            top = library.top(1)
            if not top:
                break  # Library is empty — stop (no infinite loop).
            card = top[-1]
            library.remove(card)
            card.owner = controller
            card.controller = controller
            exile.add(card)
            exiled.append(card)
            total += _mana_value(card)

        return exiled

    # ------------------------------------------------------------------
    # Step 2 — may cast any number of those spells for free
    # ------------------------------------------------------------------

    def _offer_free_casts(
        self, game: "GameState", controller: Any, exiled: list[Any]
    ) -> None:
        """Let *controller* cast any number of the *exiled* spells for free.

        Lands are not spells and are skipped.  The choice loop is optional
        ("may"): each iteration the controller decides whether to cast another
        spell, and if so chooses which exiled spell to cast for free from
        exile.  Declining ends the loop.
        """
        from engine.casting import CastingError, cast_spell_free

        chooser = getattr(controller, "choose_yes_no", None)
        picker = getattr(controller, "choose_card", None)
        if not callable(chooser) or not callable(picker):
            return

        while True:
            # Only spells still in exile that are castable (not lands).
            exile = controller.zones[Zone.EXILE]
            candidates = [
                c
                for c in exiled
                if exile.contains(c) and _is_castable_spell(c)
            ]
            if not candidates:
                return

            try:
                wants = bool(
                    chooser(
                        "Cast a spell from among the exiled cards without "
                        "paying its mana cost?"
                    )
                )
            except Exception:
                return
            if not wants:
                return

            try:
                chosen = picker(
                    candidates,
                    "spell to cast for free from among the exiled cards",
                )
            except Exception:
                return
            if chosen is None or not exile.contains(chosen):
                continue
            if not _is_castable_spell(chosen):
                continue

            try:
                cast_spell_free(game, controller, chosen, Zone.EXILE)
            except CastingError:
                # Cast failed (e.g. no legal target) — the card is rolled back
                # into exile; do not offer it again to avoid an infinite loop.
                if chosen in exiled:
                    exiled.remove(chosen)

    # ------------------------------------------------------------------
    # Step 3 — "Then exile this spell."
    # ------------------------------------------------------------------

    def _exile_this_spell(self, game: "GameState") -> None:
        """Register a stack->exile redirect so this spell is exiled on resolve.

        Reuses the sos_1 redirect helper: when this sorcery finishes resolving
        and would go to the graveyard, it is routed to exile instead.
        """
        from engine.casting import register_stack_to_graveyard_redirect

        register_stack_to_graveyard_redirect(game, self, "exile")

    # ------------------------------------------------------------------
    # Step 4 — wire the recurring paradigm copy ability
    # ------------------------------------------------------------------

    def _wire_paradigm(self, game: "GameState", controller: Any) -> None:
        """Mark first resolution + register the recurring paradigm ability."""
        from engine.paradigm import register_paradigm

        register_paradigm(
            game,
            source=self,
            controller=controller,
            factory=self.make_paradigm_copy,
            name=self.name,
        )
