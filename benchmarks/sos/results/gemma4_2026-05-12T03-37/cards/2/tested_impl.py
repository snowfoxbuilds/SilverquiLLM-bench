from engine.card import *
from engine.types import *
from engine.game import add_counter
from engine.game_state import GameState

class RancorousArchaic(Creature):
    """Rancorous Archaic."""

    def __init__(self, **kwargs):
        super().__init__(
            name="Rancorous Archaic",
            mana_cost=ManaCost.parse("{5}"),
            card_types={CardType.CREATURE},
            rules_text="""Trample, reach
Converge — This creature enters with a +1/+1 counter on it for each color of mana spent to cast it.""",
            base_power=2,
            base_toughness=2,
            keywords=Keyword.TRAMPLE | Keyword.REACH,
            **kwargs,
        )

    def on_resolve(self, game: GameState):
        # Converge: enters with a +1/+1 counter on it for each color of mana spent to cast it.
        player = game.active_player
        colors_spent = player.mana_pool.last_payment_colors
        num_colors = len(set(colors_spent))
        
        if num_colors > 0:
            add_counter(game, self, "+1/+1", num_colors)
