"""Card implementation for Scavenging Ooze."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.card_queries import choose_object
from engine.stack import same_stint, surviving_targets
from engine.types import CardType, ManaCost, ManaType

if TYPE_CHECKING:
    from engine.game_state import GameState


def _on_battlefield(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _graveyard_cards(game: Any) -> list[Any]:
    """Every card currently in any player's graveyard (the legal target set)."""
    return [
        card
        for player in game.players
        for card in game.get_graveyard(player).get_all()
    ]


def _in_graveyard(game: Any, obj: Any) -> bool:
    """Return ``True`` if *obj* is currently in some player's graveyard."""
    return any(game.get_graveyard(player).contains(obj) for player in game.players)


class ScavengingOoze(Creature):
    """Scavenging Ooze — {1}{G} — 2/2 — Ooze

    {G}: Exile target card from a graveyard. If it was a creature card,
    put a +1/+1 counter on this creature and you gain 1 life.

    FDN collector number 232.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scavenging Ooze")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Ooze"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{G}: Exile target card from a graveyard. If it was a creature "
            "card, put a +1/+1 counter on this creature and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: "GameState", src: Any, controller: Any) -> bool:
            # Instant-speed ability (rule 602.2a): the source must be on the
            # battlefield, and — mirroring "target card from a graveyard" — there
            # must be at least one card in some graveyard to target.
            if controller is None or not _on_battlefield(game, src):
                return False
            return bool(_graveyard_cards(game))

        def _targeting(
            game: "GameState", src: Any, controller: Any
        ) -> list[Any] | None:
            # Choose exactly one graveyard card at activation (rule 602.2b),
            # before {G} is paid. The card is stored on the stack object and is
            # never re-selected at resolution — a card added to a graveyard after
            # activation cannot become the target.
            cards = _graveyard_cards(game)
            if not cards:
                return None
            chosen = choose_object(
                game,
                controller,
                cards,
                "Choose a card in a graveyard to exile",
                source_card=src,
            )
            if chosen is None:
                return None
            return [chosen]

        def _cost(game: "GameState", src: Any) -> bool:
            # Paid *after* the target is chosen (rule 602.2f) — the caller runs
            # targeting first, so a no-legal-target activation spends no {G}.
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{G}"))
            return True

        def _effect(
            game: "GameState", targets: list[Any], context: Any = None
        ) -> None:
            from engine.game import add_counter, exile, gain_life

            # Revalidate the captured target: it must still be the *same*
            # graveyard card (same zone-stint). If it left the graveyard before
            # resolution — moved, exiled, drawn — do not select another card and
            # apply no reward (rule 608.2c: the sole target is illegal).
            legal = surviving_targets(
                game, context, targets, is_legal=lambda c: _in_graveyard(game, c)
            )
            chosen = legal[0] if legal else None
            if chosen is None:
                return
            is_creature = CardType.CREATURE in getattr(chosen, "card_types", set())
            exile(game, chosen)
            if not is_creature:
                return
            # Creature-card reward. "you" is the ability's activation-time
            # controller; "this creature" is the source only if it is still the
            # same battlefield permanent it was at activation (a leave-and-return
            # is a new object that gets no counter).
            controller = context.controller if context is not None else source.controller
            source_stint = context.source_instance_id if context is not None else None
            if same_stint(game, source, source_stint):
                add_counter(game, source, "+1/+1", 1)
            if controller is not None:
                gain_life(game, controller, 1)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                targeting=_targeting,
                can_activate=_can_activate,
                description="{G}: Exile target card from a graveyard. If it "
                "was a creature card, put a +1/+1 counter on this creature "
                "and you gain 1 life.",
            )
        ]
