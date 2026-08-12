"""Shared factories for the common FDN tokens.

Every FDN card that mints one of the common tokens routes through a factory
here, so each token identity has a SINGLE definition of its characteristics —
card types, subtypes, colours, and (for creatures) base power/toughness — and,
for Food and Treasure, its abilities. That matters for two reasons:

* **Gameplay honesty.** A token is a real ``Permanent`` (rule 111). Food carries
  the real "{2}, {T}, Sacrifice this token: You gain 3 life" activated ability
  and Treasure the real "{T}, Sacrifice this token: Add one mana of any color"
  mana ability, implemented as engine primitives rather than per-card no-ops.

* **Replay correlation.** The executor correlates an engine-minted token to its
  GRE grpId by matching ``(card types, subtypes, base P/T)`` and — for a
  signature several identities share (the white 1/1 Human 94158 vs the red 1/1
  Human copy 93797) — the token's explicit colour. A token minted with the exact
  characteristics ``data/replays/token_id_map.json`` records for its grpId gets
  stamped with that grpId (and so is producible, not a spurious divergence); one
  built ad hoc with a wrong or absent subtype/colour stays anonymous. Keep these
  factories in sync with the token map.

A creature token has no mana cost to derive colour from, so ``make_creature_token``
sets an explicit ``colors`` attribute — the source ``engine.protection.get_colors``
(and the executor's colour read) consult first.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from engine.card import ActivatedAbility, Artifact, Creature, ManaAbility
from engine.types import Color, Keyword, ManaCost, ManaType, Supertype


def _controller_of(obj: Any) -> Any:
    """The player who controls *obj* (falling back to its owner)."""
    return getattr(obj, "controller", None) or getattr(obj, "owner", None)


def _on_controllers_battlefield(game: Any, obj: Any) -> bool:
    """True when *obj* sits on its controller's battlefield.

    ``engine.game.sacrifice`` silently no-ops for a permanent that is not on
    its controller's battlefield, so a sacrifice-as-cost MUST verify presence
    first or the cost would report "paid" without the token ever leaving play
    (rule 602.2a: activation legality includes the source's zone).
    """
    controller = _controller_of(obj)
    if controller is None:
        return False
    return game.get_battlefield(controller).contains(obj)


class FoodToken(Artifact):
    """A Food artifact token.

    "{2}, {T}, Sacrifice this token: You gain 3 life." — a real activated
    ability. Colourless: the empty ``colors`` set is *explicit* so replay
    correlation reads it as positive colourless evidence rather than an
    undeclared colour.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Food")
        kwargs.setdefault("subtypes", {"Food"})
        kwargs.setdefault(
            "rules_text", "{2}, {T}, Sacrifice this token: You gain 3 life."
        )
        super().__init__(**kwargs)
        self.colors: set[Color] = set()
        self.is_token = True

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _can_activate(game: Any, src: Any, controller: Any) -> bool:
            # Rule 602.2a zone gate, checked by activate_ability before any
            # cost is paid: the Food must be on its controller's battlefield.
            return _on_controllers_battlefield(game, src)

        def _cost(game: Any, src: Any) -> bool:
            controller = _controller_of(src)
            if controller is None or getattr(src, "is_tapped", False):
                return False
            if not _on_controllers_battlefield(game, src):
                # Belt and braces for direct cost() drivers that skip the
                # can_activate gate: never pay {2} for an unsacrificeable token.
                return False
            two = ManaCost.parse("{2}")
            if not controller.mana_pool.can_pay(two):
                return False
            controller.mana_pool.pay(two)
            src.is_tapped = True
            from engine.game import sacrifice

            # Remember who paid so the deferred effect gains *their* life even
            # after the token has left the battlefield (it is its own cost).
            src._food_gain_controller = controller
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            controller = getattr(
                source, "_food_gain_controller", None
            ) or _controller_of(source)
            if controller is not None:
                from engine.game import gain_life

                gain_life(game, controller, 3)

        return [
            ActivatedAbility(
                cost=_cost,
                effect=_effect,
                can_activate=_can_activate,
                description="{2}, {T}, Sacrifice this token: You gain 3 life.",
            )
        ]


class TreasureToken(Artifact):
    """A Treasure artifact token.

    "{T}, Sacrifice this token: Add one mana of any color." — a real mana
    ability (resolves without using the stack). Colourless (explicit, as for
    :class:`FoodToken`).
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Treasure")
        kwargs.setdefault("subtypes", {"Treasure"})
        kwargs.setdefault(
            "rules_text", "{T}, Sacrifice this token: Add one mana of any color."
        )
        super().__init__(**kwargs)
        self.colors: set[Color] = set()
        self.is_token = True

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = _controller_of(src)
            if controller is None or getattr(src, "is_tapped", False):
                return False
            if not _on_controllers_battlefield(game, src):
                # ManaAbility has no can_activate hook, so the rule-602.2a
                # zone gate lives in the cost: never report a sacrifice paid
                # when engine.game.sacrifice would silently no-op.
                return False
            src.is_tapped = True
            from engine.game import sacrifice

            # Remember who paid so the mana lands in *their* pool even if the
            # token's controller attribute drifts after it leaves play
            # (mirrors FoodToken's beneficiary snapshot).
            src._treasure_mana_controller = controller
            sacrifice(game, controller, src)
            return True

        def _mana(game: Any) -> None:
            controller = getattr(
                source, "_treasure_mana_controller", None
            ) or _controller_of(source)
            if controller is None:
                return
            from engine.card_queries import choose_color

            letter = choose_color(
                game,
                controller,
                "Choose a color of mana to add",
                source_card=source,
            )
            controller.mana_pool.add(ManaType(letter), 1)

        return [
            ManaAbility(
                cost=_cost,
                mana_produced=_mana,
                description="{T}, Sacrifice this token: Add one mana of any color.",
            )
        ]


def make_food_token() -> FoodToken:
    """A fresh Food artifact token (see :class:`FoodToken`)."""
    return FoodToken()


def make_treasure_token() -> TreasureToken:
    """A fresh Treasure artifact token (see :class:`TreasureToken`)."""
    return TreasureToken()


def make_creature_token(
    name: str,
    subtypes: Iterable[str],
    colors: Iterable[Color],
    power: int,
    toughness: int,
    *,
    keywords: Keyword | None = None,
    supertypes: Iterable[Supertype] | None = None,
) -> Creature:
    """Build a creature token with an explicit colour identity.

    ``colors`` is an iterable of :class:`~engine.types.Color`. It is set as an
    explicit ``colors`` attribute because a token has no mana cost to derive
    colour from, and replay correlation needs the colour to tell apart
    signatures several identities share (e.g. the white 1/1 Human token 94158
    from the red 1/1 Human copy 93797).
    """
    token = Creature(
        name=name,
        subtypes=set(subtypes),
        base_power=power,
        base_toughness=toughness,
        keywords=keywords,
        supertypes=set(supertypes) if supertypes is not None else None,
    )
    token.colors = set(colors)
    token.is_token = True
    return token
