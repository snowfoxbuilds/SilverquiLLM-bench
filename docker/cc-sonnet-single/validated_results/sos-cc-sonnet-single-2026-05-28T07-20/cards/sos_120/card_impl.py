"""Card implementation for Improvisation Capstone (SOS 120)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Sorcery
from engine.types import CardType, ManaCost, Phase, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


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
            "spells from among them without paying their mana costs.\nParadigm "
            "(Then exile this spell. After you first resolve a spell with this "
            "name, you may cast a copy of it from exile without paying its mana "
            "cost at the beginning of each of your first main phases.)",
        )
        super().__init__(**kwargs)
        # Per-instance flag satisfying the test contract:
        # has_paradigm_triggered must be False before first resolution and
        # True afterwards.
        self.has_paradigm_triggered: bool = False
        # When True, this is a Paradigm copy — skip trigger re-registration.
        self.is_paradigm_copy: bool = False

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: "GameState") -> None:
        """Resolve Improvisation Capstone.

        1. Exile cards from the top of the controller's library until the
           cumulative mana value is 4 or greater.
        2. Offer free casts of those exiled cards.
        3. Exile this spell (Paradigm).
        4. Register the recurring beginning-of-main-phase trigger (once per
           controller per card name, using a game-scoped set).
        5. Set has_paradigm_triggered = True.
        """
        controller = self.controller
        if controller is None:
            return

        # --- Step 1: Exile cards from library until total MV >= 4 ---
        library = game.get_library(controller)
        exile = game.get_exile(controller)
        exiled_cards: list[Any] = []
        total_mv = 0

        while total_mv < 4:
            lib_objects = library.get_all()
            if not lib_objects:
                break
            # Top of library is last in the list (index -1).
            top_card = lib_objects[-1]
            mana_cost = getattr(top_card, "mana_cost", None)
            mv = mana_cost.cmc if mana_cost is not None else 0

            # Move from library to exile.
            library.remove(top_card)
            exile.add(top_card)
            exiled_cards.append(top_card)
            total_mv += mv

        # --- Step 2: Offer free casts of the exiled cards ---
        self._offer_free_casts(game, controller, exiled_cards)

        # --- Step 3: Exile this spell (Paradigm) ---
        self._exile_self(game, controller)

        # --- Step 4 & 5: Register paradigm trigger (first time only).
        # Use a game-scoped set keyed by (controller id, card name) so that
        # copies — which are fresh instances with has_paradigm_triggered=False
        # — do not register additional triggers.  Also skip if this instance
        # was explicitly marked as a Paradigm copy.
        _key = (id(controller), self.name)
        if not getattr(game, "paradigm_registered", None):
            game.paradigm_registered = set()  # type: ignore[union-attr]

        should_register = (
            not self.is_paradigm_copy
            and _key not in game.paradigm_registered
        )
        if should_register:
            self._register_paradigm_trigger(game, controller)
            game.paradigm_registered.add(_key)

        self.has_paradigm_triggered = True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _offer_free_casts(
        self,
        game: "GameState",
        controller: Any,
        exiled_cards: list[Any],
    ) -> None:
        """Offer the controller a free cast of each card in *exiled_cards*."""
        if not exiled_cards:
            return

        # Build a list of castable spells (non-land only).
        castable = [
            c for c in exiled_cards
            if CardType.LAND not in getattr(c, "card_types", set())
        ]
        if not castable:
            return

        # The controller may cast any number — iterate until they decline.
        remaining = list(castable)
        while remaining:
            # Ask if the controller wants to cast a spell.
            try:
                wants_to_cast = controller.choose_yes_no(
                    "You may cast a spell from among the exiled cards without "
                    "paying its mana cost."
                )
            except Exception:
                # Default to no when no scripted answer is available so we
                # do not enter an infinite loop.
                break

            if not wants_to_cast:
                break

            # Ask which spell to cast.
            try:
                chosen = controller.choose(
                    remaining,
                    "Choose a spell to cast for free from exile",
                )
            except Exception:
                chosen = remaining[0]

            if chosen is None or chosen not in remaining:
                break

            remaining.remove(chosen)

            # Cast the chosen spell from exile using the free-cast pipeline.
            from engine.casting import cast_spell_free
            cast_spell_free(game, controller, chosen, Zone.EXILE)

    def _exile_self(self, game: "GameState", controller: Any) -> None:
        """Move this spell from wherever it is to exile (Paradigm)."""
        owner = getattr(self, "owner", controller) or controller

        # Search all zones for self and move to exile.
        dest_exile = owner.zones[Zone.EXILE]

        for player in game.players:
            for zone in Zone:
                if zone == Zone.EXILE:
                    continue
                try:
                    zone_container = player.zones[zone]
                    if zone_container.contains(self):
                        zone_container.remove(self)
                        dest_exile.add(self)
                        return
                except (KeyError, AttributeError):
                    continue

        # If the spell is already in exile or not found anywhere — no-op.

    def _register_paradigm_trigger(
        self,
        game: "GameState",
        controller: Any,
    ) -> None:
        """Register the recurring beginning-of-main-phase trigger.

        At the beginning of each of the controller's precombat main phases,
        they may cast a copy of this spell from exile without paying its
        mana cost.
        """
        from engine.events import BeginningOfMainPhaseTriggeredEvent
        from engine.triggers import TriggerRegistration

        source = self

        def _condition(
            g: "GameState", event: BeginningOfMainPhaseTriggeredEvent
        ) -> bool:
            # Fire only for the controller's precombat main phase.
            return (
                event.active_player is controller
                and event.phase == Phase.PRECOMBAT_MAIN
            )

        def _effect(g: "GameState") -> None:
            """Offer the controller a free cast of a copy from exile."""
            try:
                wants_to_cast = controller.choose_yes_no(
                    "You may cast a copy of Improvisation Capstone from exile "
                    "without paying its mana cost."
                )
            except Exception:
                wants_to_cast = False

            if not wants_to_cast:
                return

            # Create a copy of the spell and mark it as a Paradigm copy so
            # that its on_resolve does NOT register yet another trigger.
            copy = ImprovisationCapstone(
                owner=controller, controller=controller
            )
            copy.is_paradigm_copy = True
            # The copy is placed in the controller's exile zone before casting.
            controller.zones[Zone.EXILE].add(copy)
            try:
                from engine.casting import cast_spell_free
                cast_spell_free(g, controller, copy, Zone.EXILE)
            except Exception:
                # If casting failed, remove the copy from exile.
                try:
                    controller.zones[Zone.EXILE].remove(copy)
                except Exception:
                    pass

        game.trigger_manager.register(
            TriggerRegistration(
                event_type=BeginningOfMainPhaseTriggeredEvent,
                condition=_condition,
                effect=_effect,
                source=source,
                controller=controller,
            )
        )
