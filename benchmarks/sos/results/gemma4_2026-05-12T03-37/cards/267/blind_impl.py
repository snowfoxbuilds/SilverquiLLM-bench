from engine.card import *
from engine.types import *
from engine.abilities import tap_cost
from engine.game_state import GameState

class Plains(Land):
    """Plains."""

    def __init__(self, **kwargs):
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Plains"}
        super().__init__(
            name="Plains",
            card_types={CardType.LAND},
            rules_text="""({T}: Add {W}.)""",
            **kwargs,
        )

    def get_mana_abilities(self) -> list[ManaAbility]:
        """Return a single mana ability: {T}: Add {W}."""
        source = self

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.WHITE, 1)

        return [
            ManaAbility(
                cost=tap_cost,
                mana_produced=_effect,
                description="{T}: Add {W}.",
            )
        ]
