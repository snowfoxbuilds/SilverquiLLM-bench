"""Card implementation for Ral Zarek, Guest Lecturer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import LoyaltyAbility, Planeswalker
from engine.types import CardType, ManaCost, ManaType, Supertype, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer — {1}{B}{B} — 3 loyalty.

    +1: Surveil 2.
    −1: Any number of target players each discard a card.
    −2: Return target creature card with mana value 3 or less from your
        graveyard to the battlefield.
    −7: Flip five coins. Target opponent skips their next X turns,
        where X is the number of coins that came up heads.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Ral Zarek, Guest Lecturer')
        kwargs.setdefault('mana_cost', ManaCost.parse('{1}{B}{B}'))
        kwargs.setdefault('starting_loyalty', 3)
        kwargs.setdefault('supertypes', set())
        kwargs['supertypes'] = (kwargs.get('supertypes') or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault('subtypes', set())
        kwargs['subtypes'] = (kwargs.get('subtypes') or set()) | {'Ral'}
        kwargs.setdefault(
            'rules_text',
            '+1: Surveil 2.\n'
            '\u22121: Any number of target players each discard a card.\n'
            '\u22122: Return target creature card with mana value 3 or less '
            'from your graveyard to the battlefield.\n'
            '\u22127: Flip five coins. Target opponent skips their next X turns, '
            'where X is the number of coins that came up heads.',
        )
        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Planeswalker loyalty abilities
    # ------------------------------------------------------------------

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus1(game: Any) -> None:
            """Surveil 2 — look at top 2 cards, choose which go to graveyard.

            Uses the controller's scripted choice mechanism. The script should
            contain the card objects that go to graveyard. Cards not chosen
            stay on top of the library. When the script is exhausted, no more
            cards are moved.
            """
            controller = pw.controller
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            graveyard = controller.zones[Zone.GRAVEYARD]
            cards = library.get_all()
            to_surveil = cards[-2:] if len(cards) >= 2 else cards[:]
            if not to_surveil:
                return

            # Pop scripted choices one at a time: each popped value is a card
            # to put into the graveyard. Stop when script is exhausted.
            to_graveyard: list[Any] = []
            for _ in to_surveil:
                try:
                    chosen = controller.choose(
                        to_surveil,
                        'Surveil: choose a card to put into graveyard',
                    )
                except Exception:
                    break
                if chosen is not None and chosen in to_surveil:
                    to_graveyard.append(chosen)
                else:
                    break

            for card in to_graveyard:
                if library.contains(card):
                    library.remove(card)
                    graveyard.add(card)

            # Remaining cards stay on top of library (already there).

        def _minus1(game: Any) -> None:
            """Any number of target players each discard a card.

            Targets are chosen when ability is activated (stored on the
            stack object). Falls back to targeting all opponents if no
            explicit targets were provided.
            """
            controller = pw.controller
            if controller is None:
                return

            # Retrieve targets stored on the source during activation
            targets = getattr(pw, '_resolve_targets', None) or []
            if not targets:
                # Fallback: target all opponents
                for p in game.players:
                    if p is not controller:
                        targets.append(p)

            for player in targets:
                hand = player.zones[Zone.HAND]
                cards = hand.get_all()
                if cards:
                    # Player chooses which card to discard; default first
                    try:
                        card = player.choose_card(
                            cards, 'Choose a card to discard'
                        )
                    except Exception:
                        card = cards[0]
                    hand.remove(card)
                    player.zones[Zone.GRAVEYARD].add(card)

        def _minus2(game: Any) -> None:
            """Return target creature card with mana value 3 or less from graveyard.

            Target is chosen when ability is activated. Falls back to the
            first valid creature in graveyard if no explicit target.
            """
            controller = pw.controller
            if controller is None:
                return

            # Retrieve target stored on the source during activation
            target = getattr(pw, '_resolve_target', None)
            if target is None:
                # Fallback: pick first valid target from graveyard
                gy = controller.zones[Zone.GRAVEYARD]
                for card in gy.get_all():
                    if CardType.CREATURE in getattr(card, 'card_types', set()):
                        cmc = getattr(getattr(card, 'mana_cost', None), 'cmc', 0)
                        if cmc <= 3:
                            target = card
                            break
            if target is None:
                return

            gy = controller.zones[Zone.GRAVEYARD]
            bf = controller.zones[Zone.BATTLEFIELD]
            if gy.contains(target):
                gy.remove(target)
                target.controller = controller
                bf.add(target)

        def _minus7(game: Any) -> None:
            """Flip five coins. Target opponent skips X turns (heads count).

            Target opponent is chosen when ability is activated. Falls back
            to first opponent if no explicit target.
            """
            import random

            controller = pw.controller
            if controller is None:
                return

            # Retrieve target stored on the source during activation
            target_opponent = getattr(pw, '_resolve_target', None)
            if target_opponent is None:
                # Fallback: first opponent
                for p in game.players:
                    if p is not controller:
                        target_opponent = p
                        break
            if target_opponent is None:
                return

            rng = getattr(game, 'rng', None) or random
            heads = sum(rng.randint(0, 1) for _ in range(5))
            skip_turns = getattr(target_opponent, 'skip_turns', 0)
            target_opponent.skip_turns = skip_turns + heads

        return [
            LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description='+1: Surveil 2.'),
            LoyaltyAbility(loyalty_cost=-1, effect=_minus1, description='\u22121: Any number of target players each discard a card.'),
            LoyaltyAbility(loyalty_cost=-2, effect=_minus2, description='\u22122: Return target creature card with mana value 3 or less from your graveyard to the battlefield.'),
            LoyaltyAbility(loyalty_cost=-7, effect=_minus7, description='\u22127: Flip five coins. Target opponent skips their next X turns.'),
        ]

    # ------------------------------------------------------------------
    # Valid targets for ability (used by activation path)
    # ------------------------------------------------------------------

    def get_valid_targets_for_ability(self, game: Any, ability_index: int) -> list[Any]:
        """Return valid targets for a specific loyalty ability."""
        controller = self.controller
        if controller is None:
            return []
        if ability_index == 0:
            # +1: Surveil - no targets
            return []
        elif ability_index == 1:
            # -1: Any number of target players
            return list(game.players)
        elif ability_index == 2:
            # -2: Target creature card with mana value 3 or less in graveyard
            targets: list[Any] = []
            gy = controller.zones[Zone.GRAVEYARD]
            for card in gy.get_all():
                if CardType.CREATURE in getattr(card, 'card_types', set()):
                    cmc = getattr(getattr(card, 'mana_cost', None), 'cmc', 0)
                    if cmc <= 3:
                        targets.append(card)
            return targets
        elif ability_index == 3:
            # -7: Target opponent
            return [p for p in game.players if p is not controller]
        return []
