"""Card implementation for Hare Apparent (FDN #15)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Color, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState


class HareApparent(Creature):
    """Hare Apparent — {1}{W} — 2/2 — Rabbit Noble.

    When this creature enters, create a number of 1/1 white Rabbit creature
    tokens equal to the number of other creatures you control named Hare
    Apparent.

    A deck can have any number of cards named Hare Apparent.

    FDN collector number 15.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hare Apparent")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Rabbit", "Noble"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, create a number of 1/1 white Rabbit "
            "creature tokens equal to the number of other creatures you "
            "control named Hare Apparent.\n"
            "A deck can have any number of cards named Hare Apparent.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: "GameState") -> None:
        """ETB: one 1/1 white Rabbit per *other* Hare Apparent you control.

        ``on_resolve`` is the engine's enters-the-battlefield hook for a
        creature spell (see :func:`engine.casting._resolve_spell`): it runs
        while this card is still on the stack, so a battlefield scan
        naturally sees only the *other* creatures already in play. The
        ``obj is not self`` guard keeps the "other" semantics correct even
        when a test places this card on the battlefield before resolving.

        Note: engine-minted tokens carry no grpId identity, so replay zone
        divergences around the Rabbit tokens are expected to persist until
        the token-correlation phase — the win here is the ETB firing and the
        Hare Apparent MISSING_CARD entries clearing.
        """
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        count = sum(
            1
            for obj in game.get_battlefield(controller).get_all()
            if obj is not self
            and CardType.CREATURE in getattr(obj, "card_types", set())
            and getattr(obj, "name", None) == "Hare Apparent"
        )

        for _ in range(count):
            token = Creature(
                name="Rabbit",
                subtypes={"Rabbit"},
                base_power=1,
                base_toughness=1,
            )
            # A token has no mana cost, so its printed colour must be stated
            # explicitly (get_colors reads an explicit ``colors`` attribute
            # before falling back to coloured mana pips). The Rabbit is white.
            token.colors = {Color.WHITE}
            create_token(game, controller, token)
