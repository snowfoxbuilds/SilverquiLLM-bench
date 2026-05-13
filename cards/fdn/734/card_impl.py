"""Card implementation for HealersHawk."""

from __future__ import annotations


from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost


def make_vanilla(
    name: str,
    cost_str: str,
    power: int,
    toughness: int,
    keywords: Keyword | None = None,
    creature_types: set[str] | None = None,
) -> type[Creature]:
    """Create a :class:`~engine.card.Creature` subclass dynamically.

    The returned class, when instantiated, produces a creature with the
    specified stats, mana cost, keywords, and creature subtypes.  The
    constructor accepts the standard ``name``/``owner``/``controller``
    keyword arguments (matching :meth:`CardRegistry.create_instance`'s
    call convention).

    Args:
        name: Card name (used as the default ``name`` for instances and
            as the generated class name).
        cost_str: Mana cost string, e.g. ``"{1}{G}"``.
        power: Base power.
        toughness: Base toughness.
        keywords: Combined :class:`~engine.types.Keyword` flags, or
            ``None`` for vanilla creatures.
        creature_types: Set of creature-type subtype strings (e.g.
            ``{"Bear"}``).  ``None`` means no subtypes.

    Returns:
        A new ``Creature`` subclass.
    """
    # Capture parameters in the closure.
    _cost = ManaCost.parse(cost_str)
    _keywords = keywords if keywords is not None else Keyword(0)
    _subtypes = creature_types if creature_types is not None else set()
    _power = power
    _toughness = toughness
    _default_name = name

    class _VanillaCreature(Creature):
        __doc__ = f"{name} — {cost_str} {power}/{toughness}"

        def __init__(self, **kwargs: Any) -> None:
            kwargs.setdefault("name", _default_name)
            kwargs.setdefault("mana_cost", _cost)
            kwargs.setdefault("keywords", _keywords)
            kwargs.setdefault("base_power", _power)
            kwargs.setdefault("base_toughness", _toughness)
            if _subtypes:
                kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | _subtypes
            super().__init__(**kwargs)

    # Give the class a readable name for debugging/repr.
    _VanillaCreature.__name__ = name.replace(" ", "").replace(",", "").replace("'", "")
    _VanillaCreature.__qualname__ = _VanillaCreature.__name__

    return _VanillaCreature


HealersHawk = make_vanilla(
    "Healer's Hawk", "{W}", 1, 1,
    keywords=Keyword.FLYING | Keyword.LIFELINK,
    creature_types={"Bird"},
)


__all__ = ["HealersHawk"]
