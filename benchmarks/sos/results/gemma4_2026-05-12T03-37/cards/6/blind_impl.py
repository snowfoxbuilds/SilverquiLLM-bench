from engine.card import Instant
from engine.types import CardType, ManaCost, TargetRequirement, Zone
from engine.game import destroy

def _get_chosen_target(card, game):
    chosen = getattr(card, "chosen_targets", None)
    if chosen:
        return chosen[0]
    return getattr(card, "_resolve_target", None)

class AjanisResponse(Instant):
    """Ajani's Response."""

    def __init__(self, **kwargs):
        super().__init__(
            name="Ajani's Response",
            mana_cost=ManaCost.parse("{4}{W}"),
            card_types={CardType.INSTANT},
            rules_text="""This spell costs {3} less to cast if it targets a tapped creature.
Destroy target creature.""",
            **kwargs,
        )

    def get_targets(self, game) -> list[TargetRequirement]:
        targets = []
        for player in game.players:
            for obj in game.get_battlefield(player).get_all():
                if CardType.CREATURE in getattr(obj, "card_types", set()):
                    targets.append(obj)
        return [
            TargetRequirement(
                filter_fn=lambda obj, _t=targets: obj in _t,
                description="target creature",
                zone=Zone.BATTLEFIELD,
            )
        ]

    def cost_reduction(self, game) -> int:
        chosen = getattr(self, "chosen_targets", None)
        if not chosen:
            return 0
        
        target = chosen[0]
        if hasattr(target, "is_tapped") and target.is_tapped:
            return 3
        return 0

    def on_resolve(self, game):
        target = _get_chosen_target(self, game)
        if target is None:
            return
        for player in game.players:
            if game.get_battlefield(player).contains(target):
                if CardType.CREATURE in getattr(target, "card_types", set()):
                    destroy(game, target)
                    return
