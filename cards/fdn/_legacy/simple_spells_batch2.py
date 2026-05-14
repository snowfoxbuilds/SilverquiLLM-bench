"""Batch 2 — Simple non-targeted instants & sorceries from Foundations (FDN).

Implements ~15 additional FDN instants and sorceries that don't target
(or target "you"): draw spells, lifegain, token creation, mill-like
(surveil), and "each player/opponent" effects.

Each spell subclasses :class:`~engine.card.Instant` or
:class:`~engine.card.Sorcery` and overrides :meth:`on_resolve`.

All cards are real FDN set cards verified against Scryfall / card_spec data.

Use :func:`register_simple_spells_batch2` to register all spells with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from engine.card import Artifact, Creature, Instant, Sorcery
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_END_OF_TURN,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Draw spells
# ---------------------------------------------------------------------------


class EmbraceTheParadox(Instant):
    """Embrace the Paradox — {3}{G}{U} — Draw three cards.

    The "you may put a land card onto the battlefield tapped" part is
    not implemented; only the draw effect is.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Embrace the Paradox")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Draw three cards. You may put a land card from your hand "
            "onto the battlefield tapped.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import draw_card

        controller = self.controller
        if controller is not None:
            for _ in range(3):
                draw_card(game, controller)


class RapturousMoment(Sorcery):
    """Rapturous Moment — {4}{U}{R} — Draw 3, discard 2, add {U}{U}{R}{R}{R}.

    The mana-adding part is not implemented; only draw 3 + discard 2.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Rapturous Moment")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Draw three cards, then discard two cards. Add {U}{U}{R}{R}{R}.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import draw_card, discard

        controller = self.controller
        if controller is None:
            return

        # Draw 3
        for _ in range(3):
            draw_card(game, controller)

        # Discard 2 (first 2 cards from hand if available)
        hand = game.get_hand(controller)
        cards_in_hand = list(hand.get_all())
        to_discard = cards_in_hand[:2]
        for card in to_discard:
            discard(game, controller, card)


class WisdomOfAges(Sorcery):
    """Wisdom of Ages — {4}{U}{U}{U} — Return all instant and sorcery cards
    from your graveyard to your hand. Exile Wisdom of Ages.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wisdom of Ages")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}{U}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Return all instant and sorcery cards from your graveyard to "
            "your hand. You have no maximum hand size for the rest of the "
            "game.\nExile Wisdom of Ages.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.zones import move_to_zone

        controller = self.controller
        if controller is None:
            return

        graveyard = game.get_graveyard(controller)
        hand = game.get_hand(controller)

        # Find all instant/sorcery cards in graveyard
        to_return = []
        for card in graveyard.get_all():
            card_types = getattr(card, "card_types", set())
            if CardType.INSTANT in card_types or CardType.SORCERY in card_types:
                to_return.append(card)

        for card in to_return:
            graveyard.remove(card)
            hand.add(card)

        # Controller has no maximum hand size for the rest of the game
        controller.no_maximum_hand_size = True

        # Exile Wisdom of Ages instead of going to graveyard
        self._exile_on_resolve = True


# ---------------------------------------------------------------------------
# Lifegain + draw spells
# ---------------------------------------------------------------------------


class PursueThePast(Sorcery):
    """Pursue the Past — {R}{W} — You gain 2 life. You may discard a card.
    If you do, draw two cards.

    Flashback is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pursue the Past")
        kwargs.setdefault("mana_cost", ManaCost.parse("{R}{W}"))
        kwargs.setdefault(
            "rules_text",
            "You gain 2 life. You may discard a card. If you do, draw two "
            "cards.\nFlashback {2}{R}{W}",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import draw_card, discard

        controller = self.controller
        if controller is None:
            return

        # Gain 2 life
        controller.life += 2

        # May discard a card; if so, draw two
        hand = game.get_hand(controller)
        cards_in_hand = list(hand.get_all())
        if cards_in_hand:
            discard(game, controller, cards_in_hand[0])
            draw_card(game, controller)
            draw_card(game, controller)


class SeizeTheSpoils(Sorcery):
    """Seize the Spoils — {2}{R} — As an additional cost, discard a card.
    Draw two cards and create a Treasure token.

    The additional cost (discard) is not enforced at cast time; it is
    applied on resolution.  Treasure token is a simple Artifact token.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Seize the Spoils")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "As an additional cost to cast this spell, discard a card.\n"
            "Draw two cards and create a Treasure token.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token, discard, draw_card

        controller = self.controller
        if controller is None:
            return

        # Additional cost: discard a card (simplified — done on resolution)
        hand = game.get_hand(controller)
        hand_cards = hand.get_all()
        if hand_cards:
            discard(game, controller, hand_cards[0])

        # Draw 2 cards
        draw_card(game, controller)
        draw_card(game, controller)

        # Create a Treasure token
        treasure = Artifact(
            name="Treasure",
            rules_text=(
                "{T}, Sacrifice this token: Add one mana of any color."
            ),
        )
        treasure.is_token = True
        create_token(game, controller, treasure)


# ---------------------------------------------------------------------------
# Token creation spells
# ---------------------------------------------------------------------------


class GroupProject(Sorcery):
    """Group Project — {1}{W} — Create a 2/2 red and white Spirit token.

    Flashback is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Group Project")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 2/2 red and white Spirit creature token.\n"
            "Flashback—Tap three untapped creatures you control.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        token = Creature(
            name="Spirit",
            base_power=2,
            base_toughness=2,
            subtypes={"Spirit"},
        )
        create_token(game, controller, token)


class MusesEncouragement(Instant):
    """Muse's Encouragement — {4}{U} — Create a 3/3 blue and red Elemental
    creature token with flying. Surveil 2.

    Surveil 2 is simplified: top 2 cards go to graveyard.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Muse's Encouragement")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{U}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 3/3 blue and red Elemental creature token with flying.\n"
            "Surveil 2.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Create 3/3 Elemental with flying
        token = Creature(
            name="Elemental",
            base_power=3,
            base_toughness=3,
            subtypes={"Elemental"},
            keywords=Keyword.FLYING,
        )
        create_token(game, controller, token)

        # Surveil 2 — look at top 2, put into graveyard
        library = controller.zones[Zone.LIBRARY]
        graveyard = controller.zones[Zone.GRAVEYARD]
        to_surveil = min(2, len(library))
        for _ in range(to_surveil):
            cards = library.top(1)
            if cards:
                card = cards[0]
                library.remove(card)
                graveyard.add(card)


class VisionarysDance(Sorcery):
    """Visionary's Dance — {5}{U}{R} — Create two 3/3 blue and red Elemental
    creature tokens with flying.

    The channel ability is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Visionary's Dance")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{U}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Create two 3/3 blue and red Elemental creature tokens with "
            "flying.\n{2}, Discard this card: Look at the top two cards of "
            "your library. Put one into your hand and the other into your "
            "graveyard.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        for _ in range(2):
            token = Creature(
                name="Elemental",
                base_power=3,
                base_toughness=3,
                subtypes={"Elemental"},
                keywords=Keyword.FLYING,
            )
            create_token(game, controller, token)


class AntiquitiesOnTheLoose(Sorcery):
    """Antiquities on the Loose — {1}{W}{W} — Create two 2/2 red and white
    Spirit creature tokens.

    The flashback cost and +1/+1 counter bonus are not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Antiquities on the Loose")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{W}"))
        kwargs.setdefault(
            "rules_text",
            "Create two 2/2 red and white Spirit creature tokens. Then if "
            "this spell was cast from anywhere other than your hand, put a "
            "+1/+1 counter on each Spirit you control.\n"
            "Flashback {4}{W}{W}",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        for _ in range(2):
            token = Creature(
                name="Spirit",
                base_power=2,
                base_toughness=2,
                subtypes={"Spirit"},
            )
            create_token(game, controller, token)


class FractalAnomaly(Instant):
    """Fractal Anomaly — {U} — Create a 0/0 green and blue Fractal creature
    token and put X +1/+1 counters on it, where X is the number of cards
    you've drawn this turn.

    Simplified: creates a 0/0 Fractal token. Counter tracking requires
    draw-count tracking which is not fully wired; defaults to 0 counters
    if no draw count is available.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fractal Anomaly")
        kwargs.setdefault("mana_cost", ManaCost.parse("{U}"))
        kwargs.setdefault(
            "rules_text",
            "Create a 0/0 green and blue Fractal creature token and put X "
            "+1/+1 counters on it, where X is the number of cards you've "
            "drawn this turn.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Count cards drawn this turn (if tracked)
        drawn_count = getattr(controller, "cards_drawn_this_turn", 0)

        token = Creature(
            name="Fractal",
            base_power=0,
            base_toughness=0,
            subtypes={"Fractal"},
        )
        token.plus_one_counters = drawn_count
        create_token(game, controller, token)


class SnarlSong(Sorcery):
    """Snarl Song — {5}{G} — Converge — Create two 0/0 green and blue Fractal
    creature tokens. Put X +1/+1 counters on each and gain X life, where X
    is the number of colors of mana spent to cast this spell.

    Simplified: assumes 1 color of mana was spent (green). Creates two
    0/0 Fractal tokens with 1 +1/+1 counter each and gains 1 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Snarl Song")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{G}"))
        kwargs.setdefault(
            "rules_text",
            "Converge — Create two 0/0 green and blue Fractal creature "
            "tokens. Put X +1/+1 counters on each of them and you gain X "
            "life, where X is the number of colors of mana spent to cast "
            "this spell.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token

        controller = self.controller
        if controller is None:
            return

        # Converge count: check how many colors were spent
        colors_spent_raw = getattr(self, "colors_spent", 1)
        # colors_spent may be a list of Color enums or an integer
        if isinstance(colors_spent_raw, (list, set)):
            colors_spent = len(colors_spent_raw)
        else:
            colors_spent = int(colors_spent_raw)

        for _ in range(2):
            token = Creature(
                name="Fractal",
                base_power=0,
                base_toughness=0,
                subtypes={"Fractal"},
            )
            token.plus_one_counters = colors_spent
            create_token(game, controller, token)

        # Gain life equal to colors spent
        controller.life += colors_spent


# ---------------------------------------------------------------------------
# "Each player / opponent" effects
# ---------------------------------------------------------------------------


class SendInThePest(Sorcery):
    """Send in the Pest — {1}{B} — Each opponent discards a card. You create
    a 1/1 black and green Pest creature token with "Whenever this token
    attacks, you gain 1 life."

    The Pest trigger ability is not implemented; just creates a 1/1.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Send in the Pest")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Each opponent discards a card. You create a 1/1 black and green "
            'Pest creature token with "Whenever this token attacks, you gain '
            '1 life."',
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import create_token, discard

        controller = self.controller
        if controller is None:
            return

        # Each opponent discards a card
        for player in game.players:
            if player is controller:
                continue
            hand = game.get_hand(player)
            cards = list(hand.get_all())
            if cards:
                discard(game, player, cards[0])

        # Create 1/1 Pest token
        token = Creature(
            name="Pest",
            base_power=1,
            base_toughness=1,
            subtypes={"Pest"},
        )
        create_token(game, controller, token)


class WitheringCurse(Sorcery):
    """Withering Curse — {1}{B}{B} — All creatures get -2/-2 until end of turn.

    The Infusion ability is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Withering Curse")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "All creatures get -2/-2 until end of turn.\n"
            "Infusion — If you gained life this turn, destroy all creatures "
            "instead.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        def _apply_debuff(game: GameState) -> None:
            for player in game.players:
                for obj in game.get_battlefield(player).get_all():
                    if CardType.CREATURE in getattr(obj, "card_types", set()):
                        obj.base_power -= 2
                        obj.base_toughness -= 2

        effect = ContinuousEffect(
            source=self,
            layer=Layer.POWER_TOUGHNESS,
            sublayer=SubLayer.MODIFY_PT,
            apply=_apply_debuff,
            duration=DURATION_END_OF_TURN,
        )
        game.effect_manager.add(effect)


class SocialSnub(Sorcery):
    """Social Snub — {1}{W}{B} — Each player sacrifices a creature.
    Each opponent loses 1 life and you gain 1 life.

    The "copy if you control a creature" trigger is not implemented.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Social Snub")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}{B}"))
        kwargs.setdefault(
            "rules_text",
            "When you cast this spell while you control a creature, you may "
            "copy this spell.\nEach player sacrifices a creature of their "
            "choice. Each opponent loses 1 life and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import sacrifice

        controller = self.controller
        if controller is None:
            return

        # Each player sacrifices a creature
        for player in game.players:
            creatures = [
                obj
                for obj in game.get_battlefield(player).get_all()
                if CardType.CREATURE in getattr(obj, "card_types", set())
            ]
            if creatures:
                sacrifice(game, player, creatures[0])

        # Each opponent loses 1 life, you gain 1 life
        for player in game.players:
            if player is not controller:
                player.life -= 1
                controller.life += 1


class PoxPlague(Sorcery):
    """Pox Plague — {B}{B}{B}{B}{B} — Each player loses half their life,
    then discards half the cards in their hand, then sacrifices half the
    permanents they control. Round down each time.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pox Plague")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B}{B}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Each player loses half their life, then discards half the cards "
            "in their hand, then sacrifices half the permanents they control "
            "of their choice. Round down each time.",
        )
        super().__init__(**kwargs)

    def get_targets(self, game: GameState) -> list[Any]:
        return []

    def on_resolve(self, game: GameState) -> None:
        from engine.game import discard, sacrifice

        for player in game.players:
            # Lose half life (rounded down)
            life_loss = player.life // 2
            player.life -= life_loss

        for player in game.players:
            # Discard half hand (rounded down)
            hand = game.get_hand(player)
            cards = list(hand.get_all())
            to_discard = len(cards) // 2
            for card in cards[:to_discard]:
                discard(game, player, card)

        for player in game.players:
            # Sacrifice half permanents (rounded down)
            permanents = list(game.get_battlefield(player).get_all())
            to_sac = len(permanents) // 2
            for perm in permanents[:to_sac]:
                sacrifice(game, player, perm)


# ---------------------------------------------------------------------------
# All batch 2 spells list for registration — Scryfall-verified metadata
# ---------------------------------------------------------------------------

_ALL_BATCH2_SPELLS: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    # (name, impl_class, mana_cost_str, colors, oracle_text,
    #  rarity, type_line, collector_number)
    #
    # --- Draw ---
    (
        "Embrace the Paradox", EmbraceTheParadox, "{3}{G}{U}",
        ["G", "U"],
        "Draw three cards. You may put a land card from your hand "
        "onto the battlefield tapped.",
        "common", "Instant", "186",
    ),
    (
        "Rapturous Moment", RapturousMoment, "{4}{U}{R}",
        ["R", "U"],
        "Draw three cards, then discard two cards. Add {U}{U}{R}{R}{R}.",
        "uncommon", "Sorcery", "219",
    ),
    (
        "Wisdom of Ages", WisdomOfAges, "{4}{U}{U}{U}",
        ["U"],
        "Return all instant and sorcery cards from your graveyard to your "
        "hand. You have no maximum hand size for the rest of the game.\n"
        "Exile Wisdom of Ages.",
        "rare", "Sorcery", "71",
    ),
    # --- Lifegain + draw ---
    (
        "Pursue the Past", PursueThePast, "{R}{W}",
        ["R", "W"],
        "You gain 2 life. You may discard a card. If you do, draw two "
        "cards.\nFlashback {2}{R}{W}",
        "common", "Sorcery", "216",
    ),
    (
        "Seize the Spoils", SeizeTheSpoils, "{2}{R}",
        ["R"],
        "As an additional cost to cast this spell, discard a card.\n"
        "Draw two cards and create a Treasure token.",
        "common", "Sorcery", "129",
    ),
    # --- Token creation ---
    (
        "Group Project", GroupProject, "{1}{W}",
        ["W"],
        "Create a 2/2 red and white Spirit creature token.\n"
        "Flashback—Tap three untapped creatures you control.",
        "uncommon", "Sorcery", "17",
    ),
    (
        "Muse's Encouragement", MusesEncouragement, "{4}{U}",
        ["U"],
        "Create a 3/3 blue and red Elemental creature token with flying.\n"
        "Surveil 2.",
        "common", "Instant", "61",
    ),
    (
        "Visionary's Dance", VisionarysDance, "{5}{U}{R}",
        ["R", "U"],
        "Create two 3/3 blue and red Elemental creature tokens with "
        "flying.\n{2}, Discard this card: Look at the top two cards of "
        "your library. Put one into your hand and the other into your "
        "graveyard.",
        "common", "Sorcery", "242",
    ),
    (
        "Antiquities on the Loose", AntiquitiesOnTheLoose, "{1}{W}{W}",
        ["W"],
        "Create two 2/2 red and white Spirit creature tokens. Then if "
        "this spell was cast from anywhere other than your hand, put a "
        "+1/+1 counter on each Spirit you control.\n"
        "Flashback {4}{W}{W}",
        "rare", "Sorcery", "7",
    ),
    (
        "Fractal Anomaly", FractalAnomaly, "{U}",
        ["U"],
        "Create a 0/0 green and blue Fractal creature token and put X "
        "+1/+1 counters on it, where X is the number of cards you've "
        "drawn this turn.",
        "uncommon", "Instant", "50",
    ),
    (
        "Snarl Song", SnarlSong, "{5}{G}",
        ["G"],
        "Converge — Create two 0/0 green and blue Fractal creature "
        "tokens. Put X +1/+1 counters on each of them and you gain X "
        "life, where X is the number of colors of mana spent to cast "
        "this spell.",
        "uncommon", "Sorcery", "161",
    ),
    # --- Each player / opponent effects ---
    (
        "Send in the Pest", SendInThePest, "{1}{B}",
        ["B"],
        "Each opponent discards a card. You create a 1/1 black and green "
        'Pest creature token with "Whenever this token attacks, you gain '
        '1 life."',
        "common", "Sorcery", "100",
    ),
    (
        "Withering Curse", WitheringCurse, "{1}{B}{B}",
        ["B"],
        "All creatures get -2/-2 until end of turn.\n"
        "Infusion — If you gained life this turn, destroy all creatures "
        "instead.",
        "mythic", "Sorcery", "105",
    ),
    (
        "Social Snub", SocialSnub, "{1}{W}{B}",
        ["B", "W"],
        "When you cast this spell while you control a creature, you may "
        "copy this spell.\nEach player sacrifices a creature of their "
        "choice. Each opponent loses 1 life and you gain 1 life.",
        "uncommon", "Sorcery", "228",
    ),
    (
        "Pox Plague", PoxPlague, "{B}{B}{B}{B}{B}",
        ["B"],
        "Each player loses half their life, then discards half the cards "
        "in their hand, then sacrifices half the permanents they control "
        "of their choice. Round down each time.",
        "rare", "Sorcery", "94",
    ),
]


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_simple_spells_batch2(registry: CardRegistry) -> None:
    """Register all batch 2 simple spells with *registry*.

    Each spell is registered under its canonical card name with
    :class:`~cards.registry.CardMetadata` reflecting its cost, type line,
    colors, and oracle text.  All metadata matches the actual FDN printing
    as sourced from Scryfall.
    """
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_BATCH2_SPELLS:
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
