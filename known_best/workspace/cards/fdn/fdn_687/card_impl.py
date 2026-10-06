"""Card implementation for Demolition Field."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Land, ManaAbility
from engine.card_queries import choose_object
from engine.stack import surviving_targets
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


# region Printed abilities — generated from card_spec.json by scripts/generate_printed_classes.py; do not edit


class DemolitionFieldAbility1:
    text = '{T}: Add {C}.'


class DemolitionFieldAbility2:
    text = "{2}, {T}, Sacrifice this land: Destroy target nonbasic land an opponent controls. That land's controller may search their library for a basic land card, put it onto the battlefield, then shuffle. You may search your library for a basic land card, put it onto the battlefield, then shuffle."


# endregion Printed abilities


def _is_nonbasic_land(obj: Any) -> bool:
    return CardType.LAND in getattr(obj, "card_types", set()) and (
        Supertype.BASIC not in getattr(obj, "supertypes", set())
    )


def _on_battlefield(game: Any, obj: Any) -> bool:
    return any(game.get_battlefield(p).contains(obj) for p in game.players)


def _search_for_basic(game: GameState, player: Any, source: Any) -> None:
    """*player* may search their library for a basic land card, put it onto
    the battlefield, then shuffle."""
    library = player.zones[Zone.LIBRARY]
    basics = [
        c
        for c in library.get_all()
        if Supertype.BASIC in getattr(c, "supertypes", set())
        and CardType.LAND in getattr(c, "card_types", set())
    ]
    if not basics:
        return
    chosen = choose_object(
        game,
        player,
        basics,
        "You may search your library for a basic land card",
        source_card=source,
        optional=True,
    )
    if chosen is None:
        return
    from engine.zones import move_to_zone

    chosen.controller = player
    move_to_zone(game, chosen, Zone.LIBRARY, Zone.BATTLEFIELD)
    library.shuffle(game)


class DemolitionField(Land):
    """Demolition Field — Land.

    {T}: Add {C}.
    {2}, {T}, Sacrifice this land: Destroy target nonbasic land an opponent
    controls. That land's controller may search their library for a basic land
    card, put it onto the battlefield, then shuffle. You may search your
    library for a basic land card, put it onto the battlefield, then shuffle.

    FDN collector number 687.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Demolition Field")
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {C}.\n"
            "{2}, {T}, Sacrifice this land: Destroy target nonbasic land an "
            "opponent controls. That land's controller may search their "
            "library for a basic land card, put it onto the battlefield, then "
            "shuffle. You may search your library for a basic land card, put "
            "it onto the battlefield, then shuffle.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: GameState, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _add_colorless(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_add_colorless,
                description="{T}: Add {C}.",
                printed=DemolitionFieldAbility1,
            )
        ]

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        def _opponents_nonbasic_lands(game: GameState, controller: Any) -> list[Any]:
            return [
                obj
                for player in game.players
                for obj in game.get_battlefield(player).get_all()
                if _is_nonbasic_land(obj)
                and getattr(obj, "controller", None) is not controller
            ]

        def _can_activate(game: GameState, src: Any, controller: Any) -> bool:
            return (
                controller is not None
                and _on_battlefield(game, src)
                and not getattr(src, "is_tapped", False)
            )

        def _targeting(game: GameState, src: Any, controller: Any) -> list[Any] | None:
            candidates = _opponents_nonbasic_lands(game, controller)
            if not candidates:
                return None
            target = choose_object(
                game,
                controller,
                candidates,
                "Choose target nonbasic land an opponent controls to destroy",
                source_card=src,
            )
            return None if target is None else [target]

        def _cost(game: GameState, src: Any) -> bool:
            from engine.game import sacrifice

            controller = src.controller
            if controller is None or getattr(src, "is_tapped", False):
                return False
            if controller.mana_pool.total() < 2:
                return False
            controller.mana_pool.pay(ManaCost(generic=2))
            src.is_tapped = True
            sacrifice(game, controller, src)
            return True

        def _effect(game: GameState, targets: list[Any], context: Any = None) -> None:
            from engine.game import destroy

            you = context.controller if context is not None else None

            def _still_legal(obj: Any) -> bool:
                return _is_nonbasic_land(obj) and getattr(obj, "controller", None) is not you

            legal = surviving_targets(game, context, targets, is_legal=_still_legal)
            if not legal:
                return  # rule 608.2b: the ability doesn't resolve
            land = legal[0]
            land_controller = getattr(land, "controller", None)
            destroy(game, land)
            if land_controller is not None:
                _search_for_basic(game, land_controller, self)
            if you is not None:
                _search_for_basic(game, you, self)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                targeting=_targeting,
                can_activate=_can_activate,
                description="{2}, {T}, Sacrifice this land: Destroy target "
                "nonbasic land an opponent controls.",
                printed=DemolitionFieldAbility2,
            )
        ]
