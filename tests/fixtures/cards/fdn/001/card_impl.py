"""Real implementation for Plains."""
from benchmarks.sos.workspace.engine.card_impl import CardImpl


class Plains(CardImpl):
    """Basic Land - Plains."""

    def play(self, game, player):
        game.add_mana(player, "W")
        return True
