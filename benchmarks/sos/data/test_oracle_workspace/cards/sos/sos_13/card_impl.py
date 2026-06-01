"""Card implementation for Emeritus of Truce // Swords to Plowshares.

Oracle text (front face — Creature):
    When this creature enters, target player creates a 2/1 white and black
    Inkling creature token with flying. Then if an opponent controls more
    creatures than you, this creature becomes prepared.

Oracle text (back face — Instant, cast via prepared from exile):
    Exile target creature. Its controller gains life equal to its power.

Front face: Emeritus of Truce — {1}{W}{W} — Creature — Cat Cleric 3/3
Back face: Swords to Plowshares — {W} — Instant (cast from exile via prepared)

CMC is 3 (front face only). The back-face {W} is the alternative cost
for the prepared ability and does NOT contribute to the card's CMC.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, ManaType, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce // Swords to Plowshares — Creature — Cat Cleric.

    Front face: {1}{W}{W}, 3/3, CMC 3.
    ETB: target player creates a 2/1 white/black Inkling token with flying.
    Prepared: ability word (NOT a keyword). When prepared and in exile,
    can cast back face (Swords to Plowshares) for {W} — exile target
    creature, its controller gains life equal to its power.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        # Front face mana cost: {1}{W}{W} → CMC 3
        kwargs.setdefault("mana_cost", ManaCost(generic=1, pips={ManaType.WHITE: 2}))
        kwargs.setdefault("card_types", set())
        kwargs["card_types"] = kwargs["card_types"] | {CardType.CREATURE}
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("keywords", Keyword(0))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 2/1 white "
            "and black Inkling creature token with flying. Then if an opponent "
            "controls more creatures than you, this creature becomes prepared.",
        )
        super().__init__(**kwargs)
        # Prepared flag — ability word state, NOT a keyword
        self._prepared: bool = False
        # Tracks whether the current cast is via prepared from exile (back face)
        self._casting_back_face: bool = False

    # ------------------------------------------------------------------
    # Targeting
    # ------------------------------------------------------------------

    def get_targets(self, game: GameState) -> list[Any]:
        """Return target requirements.

        Front face (normal cast): targets a player for ETB token.
        Back face (prepared from exile): targets a creature to exile.
        Returns a list with one TargetRequirement.
        """
        if self._casting_back_face:
            # Back face targets a creature on the battlefield
            return [
                TargetRequirement(
                    filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                    description="target creature",
                    zone=Zone.BATTLEFIELD,
                )
            ]
        else:
            # Front face targets a player (for ETB token creation)
            return [
                TargetRequirement(
                    filter_fn=lambda obj: hasattr(obj, "life"),
                    description="target player",
                    zone=Zone.BATTLEFIELD,  # not used for players
                )
            ]

    # ------------------------------------------------------------------
    # Casting hooks
    # ------------------------------------------------------------------

    def can_cast(self, game: GameState) -> bool:
        """Gate casting and detect front-face vs back-face mode.

        From hand this is a normal front-face creature cast.  From exile the
        card is castable *only* as the prepared back face (Swords to
        Plowshares); a non-prepared card in exile cannot be cast at all.
        Sets ``_casting_back_face`` so ``get_targets`` returns the right
        target requirement.
        """
        controller = self.controller or self.owner
        in_exile = (
            controller is not None
            and controller.zones[Zone.EXILE].contains(self)
        )
        if in_exile:
            if not self._prepared:
                self._casting_back_face = False
                return False
            self._casting_back_face = True
            return True
        self._casting_back_face = False
        return True

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolve(self, game: GameState) -> None:
        """Resolve either front face (ETB token) or back face (exile + life).

        Front face: create a 2/1 Inkling token for the targeted player.
        Back face (prepared): exile target creature, its controller gains
        life equal to its power.
        """
        targets = getattr(self, "chosen_targets", None) or []

        if self._casting_back_face:
            # Back face: Swords to Plowshares
            self._resolve_back_face(game, targets)
        else:
            # Front face: ETB — create token for target player
            self._resolve_front_face(game, targets)

    def _resolve_front_face(self, game: GameState, targets: list[Any]) -> None:
        """Create a 2/1 Inkling token on the targeted player's battlefield."""
        target_player = targets[0] if targets else self.controller
        if target_player is None:
            return

        token = self._create_inkling_token(target_player)
        bf = target_player.zones[Zone.BATTLEFIELD]
        bf.add(token)

        # Check prepared condition after ETB
        self._check_prepared_condition(game)

    def _resolve_back_face(self, game: GameState, targets: list[Any]) -> None:
        """Exile target creature. Its controller gains life equal to its power."""
        if not targets:
            return
        target_creature = targets[0]
        if target_creature is None:
            return

        target_controller = getattr(target_creature, "controller", None)
        if target_controller is None:
            return

        # Gain life equal to target's power
        power = getattr(target_creature, "modified_power", None)
        if power is None:
            power = getattr(target_creature, "base_power", 0)
        target_controller.life += power

        # Exile the target creature
        bf = target_controller.zones[Zone.BATTLEFIELD]
        if bf.contains(target_creature):
            bf.remove(target_creature)
            exile = target_controller.zones[Zone.EXILE]
            exile.add(target_creature)

        # Unprepare after use
        self._prepared = False
        self._casting_back_face = False

    # ------------------------------------------------------------------
    # Token creation
    # ------------------------------------------------------------------

    def _create_inkling_token(self, token_owner: Any) -> Creature:
        """Create a 2/1 Inkling token with flying for the target player."""
        from engine.card import Creature as _Creature

        token = _Creature(
            name="Inkling",
            base_power=2,
            base_toughness=1,
            keywords=Keyword.FLYING,
            subtypes={"Inkling"},
            owner=token_owner,
            controller=token_owner,
        )
        token.is_token = True
        token.summoning_sick = True
        return token

    # ------------------------------------------------------------------
    # Prepared condition check
    # ------------------------------------------------------------------

    def _check_prepared_condition(self, game: GameState) -> None:
        """If an opponent controls more creatures than us, become prepared.

        MTG-correctly the "Then if…" clause is part of the ETB trigger and
        evaluates AFTER this card is already on the battlefield. Because we
        evaluate this from `on_resolve` (the engine moves the card to BF
        afterward), we count this card itself in the my_creatures total.
        """
        controller = self.controller
        if controller is None:
            return

        # +1 accounts for this card itself (about to be placed on the BF
        # by the engine after on_resolve returns).
        my_creatures = 1 + sum(
            1 for c in controller.zones[Zone.BATTLEFIELD].get_all()
            if c is not self
            and CardType.CREATURE in getattr(c, "card_types", set())
        )

        for player in game.players:
            if player is controller:
                continue
            opp_creatures = sum(
                1 for c in player.zones[Zone.BATTLEFIELD].get_all()
                if CardType.CREATURE in getattr(c, "card_types", set())
            )
            if opp_creatures > my_creatures:
                self._prepared = True
                return
