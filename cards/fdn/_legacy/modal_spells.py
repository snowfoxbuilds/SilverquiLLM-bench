"""Modal spell implementations from Foundations (FDN).

Implements 8 modal spells with "choose one" or "choose one or both" effects:

- **Abzan Charm** — {W}{B}{G} — Choose one: exile creature with power 3+,
  draw 2 lose 2, or distribute two +1/+1 counters.
- **Boros Charm** — {R}{W} — Choose one: deal 4 to player, permanents gain
  indestructible, or target creature gains double strike.
- **Dromoka's Command** — {G}{W} — Choose two: +1/+1 counter, fight,
  sacrifice enchantment, or prevent damage from instant/sorcery.
- **Austere Command** — {4}{W}{W} — Choose two: destroy all artifacts,
  destroy all enchantments, destroy creatures CMC 3 or less,
  or destroy creatures CMC 4 or greater.
- **Prismari Command** — {1}{U}{R} — Choose two: deal 2 damage, create a
  Treasure token, draw then discard, or destroy target artifact.
- **Collective Brutality** — {1}{B} — Choose one or more (escalate — discard):
  target opponent loses 2 life and you gain 2, -2/-2 to creature,
  or target opponent discards a card.
- **Sublime Epiphany** — {4}{U}{U} — Choose one or more: counter spell,
  counter ability, copy creature, draw a card, bounce nonland permanent.
- **Inscription of Insight** — {3}{U} — Kicker {2}{U}{U}: choose one
  (or all if kicked): bounce creature, scry 2 then draw 2,
  or create a 0/0 Illusion token.

Each spell subclasses :class:`~engine.card.Instant` or
:class:`~engine.card.Sorcery` and provides :meth:`get_modes` returning
:class:`~engine.card.Mode` objects describing available choices.

Use :func:`register_modal_spells` to register all modal spells with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Instant, Mode, Sorcery
from engine.types import CardType, ManaCost

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_controller(card: Any) -> Any:
    """Return the controller of a card, or None."""
    return getattr(card, "controller", None)


def _get_target(card: Any) -> Any:
    """Return the first chosen target or the _resolve_target fallback."""
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)


def _get_targets(card: Any) -> list[Any]:
    """Return chosen targets list."""
    return getattr(card, "chosen_targets", []) or []


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


def _bounce(game: Any, obj: Any) -> None:
    """Return *obj* from the battlefield to its owner's hand."""
    from engine.types import Zone
    from engine.zones import move_to_zone
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            move_to_zone(game, obj, Zone.BATTLEFIELD, Zone.HAND)
            return


# ---------------------------------------------------------------------------
# Modal instants
# ---------------------------------------------------------------------------

class AbzanCharm(Instant):
    """Abzan Charm — {W}{B}{G} — Choose one.

    - Exile target creature with power 3 or greater.
    - You draw two cards and you lose 2 life.
    - Distribute two +1/+1 counters among one or two target creatures.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Abzan Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{W}{B}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Exile target creature with power 3 or greater.\n"
            "• You draw two cards and you lose 2 life.\n"
            "• Distribute two +1/+1 counters among one or two target creatures.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Exile", description="Exile target creature with power 3 or greater."),
            Mode(name="Draw", description="You draw two cards and you lose 2 life."),
            Mode(name="Counters", description="Distribute two +1/+1 counters among one or two target creatures."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen mode."""
        mode = self.chosen_mode
        if mode is None:
            return
        if mode == 0:
            # Exile target creature with power 3 or greater.
            target = _get_target(self)
            if target is not None and _is_on_battlefield(game, target):
                from engine.game import exile
                exile(game, target)
        elif mode == 1:
            # Draw two cards and lose 2 life.
            from engine.game import draw_card
            controller = _get_controller(self)
            if controller is not None:
                draw_card(game, controller)
                draw_card(game, controller)
                controller.life -= 2
        elif mode == 2:
            # Distribute two +1/+1 counters among targets.
            targets = _get_targets(self)
            if targets:
                counters_each = 2 // len(targets)
                remainder = 2 % len(targets)
                for i, t in enumerate(targets):
                    c = counters_each + (1 if i < remainder else 0)
                    if hasattr(t, "plus_one_counters"):
                        t.plus_one_counters += c
                        t._original_plus_one_counters = t.plus_one_counters


class BorosCharm(Instant):
    """Boros Charm — {R}{W} — Choose one.

    - Boros Charm deals 4 damage to target player or planeswalker.
    - Permanents you control gain indestructible until end of turn.
    - Target creature gains double strike until end of turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Boros Charm")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one —\n"
            "• Boros Charm deals 4 damage to target player or planeswalker.\n"
            "• Permanents you control gain indestructible until end of turn.\n"
            "• Target creature gains double strike until end of turn.",
        )
        super().__init__(**kwargs)
        self.chosen_mode: int | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Damage", description="Deal 4 damage to target player or planeswalker."),
            Mode(name="Indestructible", description="Permanents you control gain indestructible until end of turn."),
            Mode(name="Double Strike", description="Target creature gains double strike until end of turn."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen mode."""
        mode = self.chosen_mode
        if mode is None:
            return
        if mode == 0:
            # Deal 4 damage to target player or planeswalker.
            from engine.game import deal_damage
            target = _get_target(self)
            if target is not None:
                deal_damage(game, self, target, 4)
        elif mode == 1:
            # Permanents you control gain indestructible until end of turn.
            from engine.types import Keyword
            controller = _get_controller(self)
            if controller is not None:
                for obj in game.get_battlefield(controller).get_all():
                    obj.keywords = obj.keywords | Keyword.INDESTRUCTIBLE
        elif mode == 2:
            # Target creature gains double strike until end of turn.
            from engine.types import Keyword
            target = _get_target(self)
            if target is not None and hasattr(target, "keywords"):
                target.keywords = target.keywords | Keyword.DOUBLE_STRIKE
class PrismariCommand(Instant):
    """Prismari Command — {1}{U}{R} — Choose two.

    - Prismari Command deals 2 damage to any target.
    - Target player creates a Treasure token.
    - Target player draws two cards, then discards two cards.
    - Destroy target artifact.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Prismari Command")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two —\n"
            "• Prismari Command deals 2 damage to any target.\n"
            "• Target player creates a Treasure token.\n"
            "• Target player draws two cards, then discards two cards.\n"
            "• Destroy target artifact.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Damage", description="Deal 2 damage to any target."),
            Mode(name="Treasure", description="Target player creates a Treasure token."),
            Mode(name="Loot", description="Target player draws two cards, then discards two cards."),
            Mode(name="Destroy Artifact", description="Destroy target artifact."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Deal 2 damage to any target.
                from engine.game import deal_damage
                target = _get_target(self)
                if target is not None:
                    deal_damage(game, self, target, 2)
            elif mode == 1:
                # Target player creates a Treasure token.
                from engine.card import Artifact
                from engine.game import create_token
                controller = _get_controller(self)
                if controller is not None:
                    token = Artifact(name="Treasure")
                    create_token(game, controller, token)
            elif mode == 2:
                # Target player draws two cards, then discards two cards.
                from engine.game import draw_card, discard
                controller = _get_controller(self)
                if controller is not None:
                    draw_card(game, controller)
                    draw_card(game, controller)
                    # Discard 2 (simplified: discard from hand if available)
                    hand = game.get_hand(controller)
                    for _ in range(2):
                        cards = hand.get_all()
                        if cards:
                            discard(game, controller, cards[0])
            elif mode == 3:
                # Destroy target artifact.
                from engine.game import destroy
                target = _get_target(self)
                if target is not None and _is_on_battlefield(game, target):
                    destroy(game, target)


class SublimeEpiphany(Instant):
    """Sublime Epiphany — {4}{U}{U} — Choose one or more.

    - Counter target spell.
    - Counter target activated or triggered ability.
    - Copy target creature you control.
    - Target player draws a card.
    - Return target nonland permanent to its owner's hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sublime Epiphany")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Choose one or more —\n"
            "• Counter target spell.\n"
            "• Counter target activated or triggered ability.\n"
            "• Copy target creature you control.\n"
            "• Target player draws a card.\n"
            "• Return target nonland permanent to its owner's hand.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Counter Spell", description="Counter target spell."),
            Mode(name="Counter Ability", description="Counter target activated or triggered ability."),
            Mode(name="Copy Creature", description="Copy target creature you control."),
            Mode(name="Draw", description="Target player draws a card."),
            Mode(name="Bounce", description="Return target nonland permanent to its owner's hand."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Counter target spell (simplified stub — would need stack access).
                pass
            elif mode == 1:
                # Counter target activated or triggered ability (simplified stub).
                pass
            elif mode == 2:
                # Copy target creature you control (simplified stub).
                pass
            elif mode == 3:
                # Target player draws a card.
                from engine.game import draw_card
                controller = _get_controller(self)
                if controller is not None:
                    draw_card(game, controller)
            elif mode == 4:
                # Return target nonland permanent to its owner's hand.
                target = _get_target(self)
                if target is not None and _is_on_battlefield(game, target):
                    _bounce(game, target)


# ---------------------------------------------------------------------------
# Modal sorceries
# ---------------------------------------------------------------------------

class DromokasCommand(Sorcery):
    """Dromoka's Command — {G}{W} — Choose two.

    - Put a +1/+1 counter on target creature.
    - Target creature you control fights target creature you don't control.
    - Target player sacrifices an enchantment.
    - Prevent all damage target instant or sorcery spell would deal this turn.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Dromoka's Command")
        kwargs.setdefault("mana_cost", ManaCost.parse("{G}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two —\n"
            "• Put a +1/+1 counter on target creature.\n"
            "• Target creature you control fights target creature you don't control.\n"
            "• Target player sacrifices an enchantment.\n"
            "• Prevent all damage target instant or sorcery spell would deal this turn.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Counter", description="Put a +1/+1 counter on target creature."),
            Mode(name="Fight", description="Target creature you control fights target creature you don't control."),
            Mode(name="Sacrifice Enchantment", description="Target player sacrifices an enchantment."),
            Mode(name="Prevent Damage", description="Prevent all damage target instant or sorcery spell would deal this turn."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Put a +1/+1 counter on target creature.
                target = _get_target(self)
                if target is not None and hasattr(target, "plus_one_counters"):
                    target.plus_one_counters += 1
                    target._original_plus_one_counters = target.plus_one_counters
            elif mode == 1:
                # Fight — target creature you control fights target creature
                # you don't control (simplified: deal damage to each other).
                targets = _get_targets(self)
                if len(targets) >= 2:
                    from engine.game import deal_damage
                    a, b = targets[0], targets[1]
                    deal_damage(game, a, b, getattr(a, "power", 0))
                    deal_damage(game, b, a, getattr(b, "power", 0))
            elif mode == 2:
                # Target player sacrifices an enchantment.
                from engine.game import sacrifice
                target = _get_target(self)
                if target is not None:
                    bf = game.get_battlefield(target) if hasattr(target, "zones") else None
                    if bf is not None:
                        for obj in bf.get_all():
                            if CardType.ENCHANTMENT in getattr(obj, "card_types", set()):
                                sacrifice(game, target, obj)
                                break
            elif mode == 3:
                # Prevent damage — simplified stub.
                pass


class AustereCommand(Sorcery):
    """Austere Command — {4}{W}{W} — Choose two.

    - Destroy all artifacts.
    - Destroy all enchantments.
    - Destroy all creatures with mana value 3 or less.
    - Destroy all creatures with mana value 4 or greater.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Austere Command")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Choose two —\n"
            "• Destroy all artifacts.\n"
            "• Destroy all enchantments.\n"
            "• Destroy all creatures with mana value 3 or less.\n"
            "• Destroy all creatures with mana value 4 or greater.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Artifacts", description="Destroy all artifacts."),
            Mode(name="Enchantments", description="Destroy all enchantments."),
            Mode(name="Small Creatures", description="Destroy all creatures with mana value 3 or less."),
            Mode(name="Large Creatures", description="Destroy all creatures with mana value 4 or greater."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        from engine.game import destroy
        to_destroy: list[Any] = []
        for mode in modes:
            for player in game.players:
                for obj in game.get_battlefield(player).get_all():
                    if mode == 0 and CardType.ARTIFACT in getattr(obj, "card_types", set()):
                        to_destroy.append(obj)
                    elif mode == 1 and CardType.ENCHANTMENT in getattr(obj, "card_types", set()):
                        to_destroy.append(obj)
                    elif mode == 2 and CardType.CREATURE in getattr(obj, "card_types", set()):
                        cmc = getattr(obj, "mana_value", 0)
                        if cmc is None:
                            cmc = getattr(obj.mana_cost, "mana_value", 0) if obj.mana_cost else 0
                        if cmc <= 3:
                            to_destroy.append(obj)
                    elif mode == 3 and CardType.CREATURE in getattr(obj, "card_types", set()):
                        cmc = getattr(obj, "mana_value", 0)
                        if cmc is None:
                            cmc = getattr(obj.mana_cost, "mana_value", 0) if obj.mana_cost else 0
                        if cmc >= 4:
                            to_destroy.append(obj)
        for obj in to_destroy:
            if _is_on_battlefield(game, obj):
                destroy(game, obj)


class CollectiveBrutality(Sorcery):
    """Collective Brutality — {1}{B} — Choose one. Escalate — discard a card.

    - Target opponent reveals their hand. You choose a noncreature, nonland card.
      That player discards that card.
    - Target creature gets -2/-2 until end of turn.
    - Target opponent loses 2 life and you gain 2 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Collective Brutality")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Escalate — Discard a card.\n"
            "Choose one or more —\n"
            "• Target opponent reveals their hand. You choose a noncreature, "
            "nonland card from it. That player discards that card.\n"
            "• Target creature gets -2/-2 until end of turn.\n"
            "• Target opponent loses 2 life and you gain 2 life.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Discard", description="Target opponent reveals hand, discards a noncreature, nonland card."),
            Mode(name="Shrink", description="Target creature gets -2/-2 until end of turn."),
            Mode(name="Drain", description="Target opponent loses 2 life and you gain 2 life."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Target opponent discards a noncreature, nonland card (simplified stub).
                pass
            elif mode == 1:
                # Target creature gets -2/-2 until end of turn.
                target = _get_target(self)
                if target is not None and hasattr(target, "base_power"):
                    target.base_power -= 2
                    target.base_toughness -= 2
            elif mode == 2:
                # Target opponent loses 2 life and you gain 2 life.
                from engine.game import deal_damage
                controller = _get_controller(self)
                target = _get_target(self)
                if target is not None and hasattr(target, "life"):
                    target.life -= 2
                if controller is not None:
                    controller.life += 2


class InscriptionOfInsight(Sorcery):
    """Inscription of Insight — {3}{U} — Kicker {2}{U}{U}. Choose one (all if kicked).

    - Return up to two target creatures to their owners' hands.
    - Scry 2, then draw two cards.
    - Create an X/X blue Illusion creature token, where X is the number of cards in your hand.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Inscription of Insight")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Kicker {2}{U}{U}\nChoose one. If this spell was kicked, choose any number instead.\n"
            "• Return up to two target creatures to their owners' hands.\n"
            "• Scry 2, then draw two cards.\n"
            "• Create an X/X blue Illusion creature token, where X is the number of "
            "cards in your hand.",
        )
        super().__init__(**kwargs)
        self.chosen_modes: list[int] | None = None

    def get_modes(self) -> list[Mode]:
        return [
            Mode(name="Bounce", description="Return up to two target creatures to their owners' hands."),
            Mode(name="Draw", description="Scry 2, then draw two cards."),
            Mode(name="Token", description="Create an X/X blue Illusion creature token."),
        ]

    def on_resolve(self, game: GameState) -> None:
        """Resolve the chosen modes."""
        modes = self.chosen_modes or []
        for mode in modes:
            if mode == 0:
                # Return up to two target creatures to their owners' hands.
                targets = _get_targets(self)
                for t in targets[:2]:
                    if _is_on_battlefield(game, t):
                        _bounce(game, t)
            elif mode == 1:
                # Scry 2, then draw two cards.
                from engine.game import draw_card
                controller = _get_controller(self)
                if controller is not None:
                    # Simplified: skip scry, just draw 2.
                    draw_card(game, controller)
                    draw_card(game, controller)
            elif mode == 2:
                # Create an X/X blue Illusion creature token.
                from engine.card import Creature
                from engine.game import create_token
                controller = _get_controller(self)
                if controller is not None:
                    hand = game.get_hand(controller)
                    x = len(hand.get_all())
                    token = Creature(name="Illusion", base_power=x, base_toughness=x)
                    create_token(game, controller, token)


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_MODAL_SPELLS: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    ("Abzan Charm", AbzanCharm, "{W}{B}{G}",
     ["W", "B", "G"],
     "Choose one — Exile creature power 3+; Draw 2, lose 2; Distribute +1/+1 counters.",
     "uncommon", "Instant", ""),
    ("Boros Charm", BorosCharm, "{R}{W}",
     ["R", "W"],
     "Choose one — 4 damage to player/pw; Indestructible; Double strike.",
     "uncommon", "Instant", ""),
    ("Prismari Command", PrismariCommand, "{1}{U}{R}",
     ["U", "R"],
     "Choose two — 2 damage; Treasure token; Loot 2; Destroy artifact.",
     "rare", "Instant", ""),
    ("Sublime Epiphany", SublimeEpiphany, "{4}{U}{U}",
     ["U"],
     "Choose one or more — Counter spell; Counter ability; Copy creature; Draw; Bounce.",
     "rare", "Instant", ""),
    ("Dromoka's Command", DromokasCommand, "{G}{W}",
     ["G", "W"],
     "Choose two — +1/+1 counter; Fight; Sacrifice enchantment; Prevent damage.",
     "rare", "Sorcery", ""),
    ("Austere Command", AustereCommand, "{4}{W}{W}",
     ["W"],
     "Choose two — Destroy artifacts; Destroy enchantments; Destroy small creatures; Destroy large creatures.",
     "rare", "Sorcery", ""),
    ("Collective Brutality", CollectiveBrutality, "{1}{B}",
     ["B"],
     "Escalate. Choose one or more — Discard; -2/-2; Drain 2.",
     "rare", "Sorcery", ""),
    ("Inscription of Insight", InscriptionOfInsight, "{3}{U}",
     ["U"],
     "Kicker. Choose one (all if kicked) — Bounce; Scry+Draw; X/X token.",
     "rare", "Sorcery", ""),
]


def register_modal_spells(registry: CardRegistry) -> None:
    """Register all modal spells with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_MODAL_SPELLS:
        metadata = CardMetadata(
            name=card_name,
            mana_cost_str=cost_str,
            type_line=type_line,
            oracle_text=oracle_text,
            power=None,
            toughness=None,
            colors=colors,
            keywords=[],
            rarity=rarity,
            set_code="fdn",
            collector_number=collector_number,
        )
        registry.register(card_name, impl_class, metadata)
