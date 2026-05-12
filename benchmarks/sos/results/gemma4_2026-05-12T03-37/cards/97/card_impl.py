from engine.card import *
from engine.types import *
from engine.game import draw_card, discard
from engine.zones import move_to_zone, move_zone
from engine.game_state import GameState
import random

class RalZarekGuestLecturer(Planeswalker):
    """Ral Zarek, Guest Lecturer."""

    def __init__(self, **kwargs):
        super().__init__(
            name="Ral Zarek, Guest Lecturer",
            mana_cost=ManaCost.parse("{1}{B}{B}"),
            card_types={CardType.PLANESWALKER},
            rules_text="""+1: Surveil 2.
−1: Any number of target players each discard a card.
−2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.
−7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.""",
            starting_loyalty=3,
            **kwargs,
        )

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        return [
            LoyaltyAbility(
                loyalty_cost=1,
                effect=self._surveil_2,
                description="+1: Surveil 2.",
            ),
            LoyaltyAbility(
                loyalty_cost=-1,
                effect=self._discard_any,
                description="-1: Any number of target players each discard a card.",
            ),
            LoyaltyAbility(
                loyalty_cost=-2,
                effect=self._reanimate,
                description="-2: Return target creature card with mana value 3 or less from your graveyard to the battlefield.",
            ),
            LoyaltyAbility(
                loyalty_cost=-7,
                effect=self._skip_turns,
                description="-7: Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads.",
            ),
        ]

    def _surveil_2(self, game: GameState) -> None:
        player = self.controller
        library = player.zones[Zone.LIBRARY]
        for _ in range(2):
            if len(library) == 0:
                break
            card = library.top(1)[0]
            choice = player.choose(["bottom", "graveyard"], f"Surveil: put {card.name} on bottom or in graveyard")
            if choice == "bottom":
                move_zone(card, library, library, position="bottom")
            else:
                move_to_zone(game, card, Zone.LIBRARY, Zone.GRAVEYARD)

    def _discard_any(self, game: GameState) -> None:
        # "Any number of target players each discard a card."
        # In a 2-player game, options are [player0, player1].
        # The active player chooses which players to target.
        players = game.players
        targets = self.controller.choose(["some", "all", "none"], "Choose target players to discard")
        
        if targets == "none":
            return
        
        if targets == "all":
            target_list = players
        elif targets == "some":
            # For simplicity in this engine, "some" will just be the opponent.
            target_list = [game.non_active_player]
        else:
            target_list = players

        for p in target_list:
            hand = p.zones[Zone.HAND]
            if len(hand) > 0:
                # Player chooses what to discard
                card = p.choose_card(hand.get_all(), "Choose card to discard")
                discard(game, p, card)

    def _reanimate(self, game: GameState) -> None:
        player = self.controller
        graveyard = player.zones[Zone.GRAVEYARD]
        
        # Find creature cards with mana value 3 or less
        valid_targets = [
            card for card in graveyard.get_all()
            if CardType.CREATURE in getattr(card, "card_types", set())
            and card.mana_cost.cmc <= 3
        ]
        
        if not valid_targets:
            return
            
        target_card = player.choose_card(valid_targets, "Choose creature card with MV <= 3 to return")
        move_to_zone(game, target_card, Zone.GRAVEYARD, Zone.BATTLEFIELD)

    def _skip_turns(self, game: GameState) -> None:
        # "Flip five coins. Target opponent skips their next X turns, where X is the number of coins that came up heads."
        opponent = game.non_active_player
        heads = 0
        for _ in range(5):
            if random.random() < 0.5:
                heads += 1
        
        opponent.turns_to_skip = heads
