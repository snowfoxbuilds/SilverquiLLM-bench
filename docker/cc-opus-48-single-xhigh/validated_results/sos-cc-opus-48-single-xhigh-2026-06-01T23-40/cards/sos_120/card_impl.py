"""Card implementation for Improvisation Capstone (SOS 120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


def _mana_value(card: Any) -> int:
    """Return the mana value (CMC) of *card*, treating missing costs as 0."""
    mana_cost = getattr(card, "mana_cost", None)
    if mana_cost is None:
        return 0
    return int(getattr(mana_cost, "cmc", 0) or 0)


def _is_nonland_spell(card: Any) -> bool:
    """Return ``True`` if *card* is a castable nonland spell (never a land)."""
    card_types = getattr(card, "card_types", set())
    return CardType.LAND not in card_types


class ImprovisationCapstone(Sorcery):
    """Improvisation Capstone — {5}{R}{R} — Sorcery — Lesson.

    Exile cards from the top of your library until you exile cards with total
    mana value 4 or greater. You may cast any number of spells from among them
    without paying their mana costs.
    Paradigm (Then exile this spell. After you first resolve a spell with this
    name, you may cast a copy of it from exile without paying its mana cost at
    the beginning of each of your first main phases.)

    SOS collector number 120.
    """

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
        # Explicit colors (KEY_DECISIONS sos_13).
        self.colors = ["R"]
        # Card-level marker advertising the Paradigm keyword (not an evergreen
        # engine Keyword flag).
        self.paradigm = True

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Improvisation Capstone.

        1. Exile cards from the top of the controller's library until the
           cumulative mana value of the exiled pile is 4 or greater.
        2. Offer the controller a free cast (no mana) of each nonland spell
           among the freshly exiled pile.
        3. Paradigm: self-exile this spell on resolution, and on the FIRST
           resolution schedule a recurring precombat-main-phase effect that
           offers a free copy from exile.
        """
        controller = self.controller
        if controller is None:
            return

        # --- Clause 1: exile-until-MV-4 -------------------------------------
        exiled_pile = self._exile_until_mana_value_four(game, controller)

        # --- Clause 2: free-cast from among the exiled pile ----------------
        self._offer_free_casts(game, controller, exiled_pile)

        # --- Clause 3: Paradigm self-exile + recurring copy trigger --------
        # "Then exile this spell" — route the resolving Capstone to exile
        # instead of the graveyard (sos_1 opt-in honoured by casting pipeline).
        self._exile_instead_of_graveyard = True  # type: ignore[attr-defined]
        self._schedule_paradigm_copy(game, controller)

    # ------------------------------------------------------------------
    # Clause 1 — exile until total mana value >= 4
    # ------------------------------------------------------------------

    def _exile_until_mana_value_four(
        self, game: "GameState", controller: "Player"
    ) -> list[Any]:
        """Exile top library cards until cumulative MV >= 4.

        Returns the list of cards exiled by this call (in exile order). MV-0
        cards add 0 and do not stop the loop. An empty / too-small library
        terminates safely without raising.
        """
        library = game.get_library(controller)
        exile = game.get_exile(controller)

        exiled: list[Any] = []
        total = 0
        while total < 4:
            top = library.top(1)
            if not top:
                # Library emptied before reaching MV 4 — safe termination.
                break
            card = top[0]
            library.remove(card)
            exile.add(card)
            exiled.append(card)
            total += _mana_value(card)
        return exiled

    # ------------------------------------------------------------------
    # Clause 2 — cast any number of the exiled spells for free
    # ------------------------------------------------------------------

    def _offer_free_casts(
        self, game: "GameState", controller: "Player", exiled_pile: list[Any]
    ) -> None:
        """Offer the controller a free cast of each nonland spell in the pile.

        Uses the sos_1 ``choose_yes_no``-per-eligible-spell convention: lands
        are skipped entirely; for each remaining nonland card the controller is
        asked whether to cast it for free from exile. Accepted spells are
        free-cast (``cast_spell_free`` from ``Zone.EXILE``); declined cards stay
        in exile.
        """
        from engine.casting import cast_spell_free, CastingError

        for card in exiled_pile:
            if not _is_nonland_spell(card):
                # Lands can never be cast — skip without asking.
                continue
            # The card must still be in exile (it could have been moved by an
            # earlier free cast, though pile entries are distinct).
            if not game.get_exile(controller).contains(card):
                continue
            if not controller.choose_yes_no(
                f"Cast {getattr(card, 'name', 'a spell')!r} from exile without "
                "paying its mana cost?"
            ):
                continue
            try:
                cast_spell_free(game, controller, card, Zone.EXILE)
            except CastingError:
                # If the spell cannot legally be cast, leave it in exile.
                continue

    # ------------------------------------------------------------------
    # Clause 3 — Paradigm recurring copy trigger
    # ------------------------------------------------------------------

    # Name of the additive guard attribute stowed on the game state. It holds
    # the set of controllers for whom the recurring Paradigm offer has already
    # been armed.
    _PARADIGM_ARMED_ATTR = "_improvisation_capstone_paradigm_armed"

    def _schedule_paradigm_copy(
        self, game: "GameState", controller: "Player"
    ) -> None:
        """Arm the recurring Paradigm copy offer for the controller — ONCE.

        Paradigm reads "...you may cast a copy of it from exile... at the
        beginning of EACH of your first main phases", i.e. exactly ONE recurring
        offer per controller. Because the recurring callback re-schedules itself
        (the deferred surface is one-shot) AND a freshly cast free copy runs its
        own ``on_resolve`` when it later resolves, arming must be idempotent:
        without a guard each resolved copy would register a second independent
        self-perpetuating chain, multiplying the offer without bound.

        We therefore key an "already armed" set by controller on the game state
        (an additive attribute). The first resolution of a spell with this name
        for a given controller arms exactly one recurring chain; every later
        resolution — including the resolution of free copies — is a no-op.

        The sos_57 ``schedule_main_phase_deferred_effect`` surface is one-shot,
        so the single armed callback RE-SCHEDULES itself each time it fires —
        making the lone offer recur at the beginning of every precombat main
        phase. When it fires, the controller may cast a free copy of the
        Capstone from exile.
        """
        # --- Idempotent per-controller arming guard ------------------------
        armed = getattr(game, self._PARADIGM_ARMED_ATTR, None)
        if armed is None:
            armed = set()
            setattr(game, self._PARADIGM_ARMED_ATTR, armed)
        if controller in armed:
            # Already armed for this controller — do NOT add a second chain.
            return
        armed.add(controller)

        capstone = self

        def _offer_copy(g: "GameState") -> None:
            # Re-schedule first so the recurring offer persists for the next
            # precombat main phase even after this one fires (the deferred
            # delivery removes one-shot entries before running callbacks).
            g.schedule_main_phase_deferred_effect(
                controller, _offer_copy, precombat=True
            )

            if not controller.choose_yes_no(
                "Cast a copy of Improvisation Capstone from exile without "
                "paying its mana cost?"
            ):
                return

            capstone._cast_free_copy(g, controller)

        game.schedule_main_phase_deferred_effect(
            controller, _offer_copy, precombat=True
        )

    def _cast_free_copy(self, game: "GameState", controller: "Player") -> None:
        """Cast a free copy of Improvisation Capstone from exile.

        Mirrors the casting pipeline by building a fresh Capstone instance (a
        copy) and free-casting it. The copy carries the same Paradigm self-exile
        rider so its own resolution behaves identically.
        """
        from engine.casting import cast_spell_free, CastingError

        copy = ImprovisationCapstone(owner=controller, controller=controller)
        # Place the copy into exile so it can be cast "from exile".
        game.get_exile(controller).add(copy)
        try:
            cast_spell_free(game, controller, copy, Zone.EXILE)
        except CastingError:
            # Could not cast — remove the dangling copy from exile.
            exile = game.get_exile(controller)
            if exile.contains(copy):
                exile.remove(copy)
