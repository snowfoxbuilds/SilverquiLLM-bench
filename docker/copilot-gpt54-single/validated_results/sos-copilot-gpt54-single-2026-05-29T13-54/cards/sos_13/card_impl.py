"""Card implementation for Emeritus of Truce // Swords to Plowshares."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import CardFace, Creature, Instant
from engine.events import EntersBattlefieldTriggeredEvent
from engine.stack import PreparedAction
from engine.types import CardType, Color, Keyword, ManaCost, TargetRequirement, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


def _self_etb_condition(source: Any):
    """Return a condition that matches only when *source* enters."""

    def _condition(game: Any, event: EntersBattlefieldTriggeredEvent) -> bool:
        return event.permanent is source

    return _condition


def _get_first_chosen_target(card: Any) -> Any | None:
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return None


def _count_creatures(game: "GameState", player: Any) -> int:
    return sum(
        1
        for obj in game.get_battlefield(player).get_all()
        if CardType.CREATURE in getattr(obj, "card_types", set())
    )


def _is_creature_on_battlefield(game: "GameState", obj: Any) -> bool:
    if obj is None or CardType.CREATURE not in getattr(obj, "card_types", set()):
        return False
    return any(game.get_battlefield(player).contains(obj) for player in game.players)


def _choose_target_player(
    game: "GameState",
    _event: EntersBattlefieldTriggeredEvent,
    source: Any,
) -> list[Any] | None:
    controller = getattr(source, "controller", None) or game.active_player
    players = list(game.players)
    if not players:
        return None
    if controller is None or not hasattr(controller, "choose_target"):
        return [players[0]]
    chosen = controller.choose_target(players, "target player")
    if chosen not in players:
        return None
    return [chosen]


class SwordsToPlowshares(Instant):
    """Embedded instant spell used by Emeritus of Truce."""

    type_line = "Instant"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}"))
        kwargs.setdefault(
            "rules_text",
            "Exile target creature. Its controller gains life equal to its power.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: "GameState") -> list[Any]:
        return [
            TargetRequirement(
                filter_fn=lambda obj: CardType.CREATURE in getattr(obj, "card_types", set()),
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def on_resolve(self, game: "GameState") -> None:
        from engine.game import exile

        target = _get_first_chosen_target(self)
        if not _is_creature_on_battlefield(game, target):
            return

        target_controller = getattr(target, "controller", None)
        life_to_gain = max(0, getattr(target, "power", getattr(target, "base_power", 0)))
        exile(game, target)
        if target_controller is not None and hasattr(target_controller, "life"):
            target_controller.life += life_to_gain


class EmeritusOfTruceSwordsToPlowshares(Creature):
    """Emeritus of Truce with a prepared Swords to Plowshares spell side."""

    spell_face = CardFace(
        name="Swords to Plowshares",
        mana_cost=ManaCost.parse("{W}"),
        type_line="Instant",
    )
    spell_side = spell_face
    spell_name = spell_face.name
    spell_mana_cost = spell_face.mana_cost
    spell_type_line = spell_face.type_line

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Emeritus of Truce // Swords to Plowshares")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault("subtypes", {"Cat", "Cleric"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, target player creates a 1/1 white and black "
            "Inkling creature token with flying. Then if an opponent controls more "
            "creatures than you, this creature becomes prepared. (While it's prepared, "
            "you may cast a copy of its spell. Doing so unprepares it.)",
        )
        super().__init__(**kwargs)
        self.is_prepared: bool = False

    @property
    def embedded_spell(self) -> SwordsToPlowshares:
        """Return a fresh castable representation of the spell side."""
        return SwordsToPlowshares(owner=self.owner, controller=self.controller)

    def register_triggers(self, game: "GameState") -> None:
        from engine.game import create_token
        from engine.triggers import TriggerRegistration

        source = self

        def _effect(game: "GameState") -> None:
            target_player = _get_first_chosen_target(source)
            controller = getattr(source, "controller", None)
            if target_player is None:
                return

            token = Creature(
                name="Inkling",
                subtypes={"Inkling"},
                keywords=Keyword.FLYING,
                base_power=1,
                base_toughness=1,
            )
            token.colors = {Color.WHITE, Color.BLACK}
            create_token(game, target_player, token)

            if controller is None:
                return
            your_creature_count = _count_creatures(game, controller)
            source.is_prepared = any(
                _count_creatures(game, player) > your_creature_count
                for player in game.players
                if player is not controller
            )

        controller = self.controller or game.active_player
        game.trigger_manager.register(
            TriggerRegistration(
                event_type=EntersBattlefieldTriggeredEvent,
                condition=_self_etb_condition(self),
                effect=_effect,
                source=self,
                controller=controller,
                choose_targets=_choose_target_player,
            )
        )

    def get_prepared_actions(self, game: "GameState") -> list[Any]:
        from engine.casting import cast_spell_copy, spell_has_legal_targets

        controller = self.controller
        if controller is None or not self.is_prepared:
            return []
        if not game.get_battlefield(controller).contains(self):
            return []

        spell = self.embedded_spell
        if not spell_has_legal_targets(game, spell):
            return []

        source = self

        def _perform(game: "GameState", *, targets: list[Any] | None = None):
            stack_obj = cast_spell_copy(
                game,
                controller,
                source.embedded_spell,
                chosen_targets=targets,
            )
            source.is_prepared = False
            return stack_obj

        return [
            PreparedAction(
                source=self,
                controller=controller,
                spell=spell,
                description=f"Cast a copy of {self.spell_name}",
                perform_fn=_perform,
            )
        ]
