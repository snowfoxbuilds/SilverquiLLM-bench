from engine.card import *
from engine.types import *


class Plains(Land):
    """Plains."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name", "Plains")
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.BASIC}
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Plains"}
        kwargs.setdefault("rules_text", "({T}: Add {W}.)")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game, s):
            if getattr(s, "is_tapped", False):
                return False
            s.is_tapped = True
            return True

        def _effect(game):
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.WHITE, 1)

        return [
            ManaAbility(
                cost=_tap_cost,
                mana_produced=_effect,
                description="{T}: Add {W}.",
            )
        ]
