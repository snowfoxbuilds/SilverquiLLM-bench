"""Artifact card implementations (batch 2) from Foundations (FDN).

Implements remaining FDN artifacts not covered by ``artifacts.py`` or
``equipment.py``:

- **Mana rocks**: Gilded Lotus, Carnelian Orb of Dragonkind, Heraldic Banner,
  Hedron Archive (already in batch 1 registration but re-exported here for
  completeness — actually Hedron Archive was already registered elsewhere).
- **Utility artifacts**: Banner of Kinship, Ravenous Amulet, Goblin Firebomb,
  Feldon's Cane, Soul-Guide Lantern, Sorcerous Spyglass, Mazemind Tome,
  Expedition Map, Wishclaw Talisman, Pyromancer's Goggles.
- **Artifact creatures**: Crystal Barricade, Scrawling Crawler, Campus Guide,
  Juggernaut, Darksteel Colossus, Diamond Mare, Gate Colossus, Steel Hellkite,
  Three Tree Mascot, Adaptive Automaton, Ramos Dragon Engine.
- **Equipment**: Fishing Pole, Pirate's Cutlass.
- **Vehicle**: Cultivator's Caravan.

All cards subclass :class:`~engine.card.Artifact`,
:class:`~engine.card.ArtifactCreature`, or :class:`~engine.card.Creature`.

Use :func:`register_artifacts_batch2` to register all batch-2 artifacts with a
:class:`~cards.registry.CardRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import (
    Artifact,
    ArtifactCreature,
    ActivatedAbility,
    ManaAbility,
)
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player

    from cards.registry import CardRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_on_battlefield(game: Any, obj: Any) -> bool:
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


# ---------------------------------------------------------------------------
# Mana rocks / mana-producing artifacts
# ---------------------------------------------------------------------------

class GildedLotus(Artifact):
    """Gilded Lotus — {5} — {T}: Add three mana of any one color."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gilded Lotus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault("rules_text", "{T}: Add three mana of any one color.")
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                # Simplified: add 3 colorless (color choice not modelled)
                controller.mana_pool.add(ManaType.COLORLESS, 3)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add three mana of any one color."),
        ]


class CarnelianOrbOfDragonkind(Artifact):
    """Carnelian Orb of Dragonkind — {2}{R} — {T}: Add {R}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Carnelian Orb of Dragonkind")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{R}"))
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {R}. If that mana is spent on a Dragon creature spell, "
            "it gains haste until end of turn.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add {R}."),
        ]


class HeraldicBanner(Artifact):
    """Heraldic Banner — {3} — As enters, choose a color. Creatures of that
    color get +1/+0. {T}: Add one mana of the chosen color."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Heraldic Banner")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault(
            "rules_text",
            "As this artifact enters, choose a color.\n"
            "Creatures you control of the chosen color get +1/+0.\n"
            "{T}: Add one mana of the chosen color.",
        )
        super().__init__(**kwargs)
        self.chosen_color: str | None = None

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                # Simplified: add colorless (color choice not modelled)
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add one mana of the chosen color."),
        ]


class PyromancersGoggles(Artifact):
    """Pyromancer's Goggles — {5} — Legendary — {T}: Add {R}. Copy effect."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pyromancer's Goggles")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault(
            "rules_text",
            "{T}: Add {R}. When that mana is spent to cast a red instant or sorcery "
            "spell, copy that spell and you may choose new targets for the copy.",
        )
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.RED, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add {R}."),
        ]


# ---------------------------------------------------------------------------
# Utility artifacts
# ---------------------------------------------------------------------------

class BannerOfKinship(Artifact):
    """Banner of Kinship — {5} — As enters, choose a creature type.
    Enters with fellowship counters. Chosen type gets +1/+1 per counter."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Banner of Kinship")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}"))
        kwargs.setdefault(
            "rules_text",
            "As this artifact enters, choose a creature type. This artifact enters "
            "with a fellowship counter on it for each creature you control of the "
            "chosen type.\nCreatures you control of the chosen type get +1/+1 for "
            "each fellowship counter on this artifact.",
        )
        super().__init__(**kwargs)
        self.chosen_type: str | None = None
        self.fellowship_counters: int = 0


class RavenousAmulet(Artifact):
    """Ravenous Amulet — {2} — Sacrifice creature to draw; sac self to drain."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ravenous Amulet")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault(
            "rules_text",
            "{1}, {T}, Sacrifice a creature: Draw a card and put a soul counter on "
            "this artifact. Activate only as a sorcery.\n"
            "{4}, {T}, Sacrifice this artifact: Each opponent loses life equal to "
            "the number of soul counters on this artifact.",
        )
        super().__init__(**kwargs)
        self.soul_counters: int = 0

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _sac_creature_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            # Sacrifice a creature as part of the cost
            from engine.game import sacrifice
            controller = source.controller
            if controller is not None:
                bf = game.get_battlefield(controller)
                creatures = [
                    o for o in bf.get_all()
                    if CardType.CREATURE in getattr(o, "card_types", set())
                ]
                if creatures:
                    sacrifice(game, controller, creatures[0])
            return True

        def _sac_creature_effect(game: Any) -> None:
            from engine.game import draw_card
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)
                source.soul_counters += 1

        def _drain_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _drain_effect(game: Any) -> None:
            from engine.game import sacrifice
            controller = source.controller
            if controller is not None:
                # Sacrifice this artifact
                sacrifice(game, controller, source)
                for p in game.players:
                    if p is not controller:
                        p.life -= source.soul_counters

        return [
            ActivatedAbility(
                cost=_sac_creature_cost,
                effect=_sac_creature_effect,
                description="{1}, {T}, Sacrifice a creature: Draw a card and put a soul counter.",
            ),
            ActivatedAbility(
                cost=_drain_cost,
                effect=_drain_effect,
                description="{4}, {T}, Sacrifice: Each opponent loses life equal to soul counters.",
            ),
        ]


class GoblinFirebomb(Artifact):
    """Goblin Firebomb — {1} — Flash. {7}, {T}, Sacrifice: Destroy target permanent."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Goblin Firebomb")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault(
            "rules_text",
            "Flash\n{7}, {T}, Sacrifice this artifact: Destroy target permanent.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import destroy
            target = getattr(source, "_resolve_target", None)
            if target is not None:
                destroy(game, target)

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{7}, {T}, Sacrifice: Destroy target permanent.",
            ),
        ]


class FeldonsCane(Artifact):
    """Feldon's Cane — {1} — {T}, Exile: Shuffle your graveyard into your library."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Feldon's Cane")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{T}, Exile this artifact: Shuffle your graveyard into your library.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import exile
            from engine.types import Zone
            controller = source.controller
            if controller is not None:
                graveyard = controller.zones[Zone.GRAVEYARD]
                library = controller.zones[Zone.LIBRARY]
                if graveyard is not None and library is not None:
                    for card in list(graveyard.get_all()):
                        graveyard.remove(card)
                        library.add(card)
                    library.shuffle()
                exile(game, source)

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{T}, Exile: Shuffle graveyard into library.",
            ),
        ]


class SoulGuideLantern(Artifact):
    """Soul-Guide Lantern — {1} — ETB: exile target card from graveyard.
    Sac: exile opponents' graveyards. Or sac to draw."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Soul-Guide Lantern")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "When this artifact enters, exile target card from a graveyard.\n"
            "{T}, Sacrifice this artifact: Exile each opponent's graveyard.\n"
            "{1}, {T}, Sacrifice this artifact: Draw a card.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _exile_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _exile_effect(game: Any) -> None:
            from engine.types import Zone
            from engine.zones import move_to_zone
            from engine.game import sacrifice
            controller = source.controller
            if controller is not None:
                # Sacrifice the Lantern as part of activation
                sacrifice(game, controller, source)
                for p in game.players:
                    if p is not controller:
                        gy = p.zones[Zone.GRAVEYARD]
                        for card in list(gy.get_all()):
                            move_to_zone(game, card, Zone.GRAVEYARD, Zone.EXILE)

        def _draw_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _draw_effect(game: Any) -> None:
            from engine.game import draw_card, sacrifice
            controller = source.controller
            if controller is not None:
                # Sacrifice the Lantern as part of activation
                sacrifice(game, controller, source)
                draw_card(game, controller)

        return [
            ActivatedAbility(
                cost=_exile_cost, effect=_exile_effect,
                description="{T}, Sacrifice: Exile each opponent's graveyard.",
            ),
            ActivatedAbility(
                cost=_draw_cost, effect=_draw_effect,
                description="{1}, {T}, Sacrifice: Draw a card.",
            ),
        ]


class SorcerousSpyglass(Artifact):
    """Sorcerous Spyglass — {2} — As enters, look at opponent's hand, choose a name.
    Activated abilities of sources with chosen name can't be activated."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Sorcerous Spyglass")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault(
            "rules_text",
            "As this artifact enters, look at an opponent's hand, then choose any "
            "card name.\nActivated abilities of sources with the chosen name can't "
            "be activated unless they're mana abilities.",
        )
        super().__init__(**kwargs)
        self.chosen_name: str | None = None


class MazemindTome(Artifact):
    """Mazemind Tome — {2} — Scry/draw with page counters; exile at 4 counters."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Mazemind Tome")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Book"}
        kwargs.setdefault(
            "rules_text",
            "{T}, Put a page counter on this artifact: Scry 1.\n"
            "{2}, {T}, Put a page counter on this artifact: Draw a card.\n"
            "When there are four or more page counters on this artifact, exile it. "
            "If you do, you gain 4 life.",
        )
        super().__init__(**kwargs)
        self.page_counters: int = 0

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _scry_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _scry_effect(game: Any) -> None:
            source.page_counters += 1
            # Scry 1: simplified — no-op (would need library peek)
            if source.page_counters >= 4:
                from engine.game import exile
                controller = source.controller
                if controller is not None:
                    controller.life += 4
                exile(game, source)

        def _draw_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _draw_effect(game: Any) -> None:
            from engine.game import draw_card
            source.page_counters += 1
            controller = source.controller
            if controller is not None:
                draw_card(game, controller)
            if source.page_counters >= 4:
                from engine.game import exile
                controller = source.controller
                if controller is not None:
                    controller.life += 4
                exile(game, source)

        return [
            ActivatedAbility(
                cost=_scry_cost, effect=_scry_effect,
                description="{T}, Put a page counter: Scry 1.",
            ),
            ActivatedAbility(
                cost=_draw_cost, effect=_draw_effect,
                description="{2}, {T}, Put a page counter: Draw a card.",
            ),
        ]


class ExpeditionMap(Artifact):
    """Expedition Map — {1} — {2}, {T}, Sacrifice: Search for a land card."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Expedition Map")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault(
            "rules_text",
            "{2}, {T}, Sacrifice this artifact: Search your library for a land card, "
            "reveal it, put it into your hand, then shuffle.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            from engine.game import sacrifice
            from engine.types import Zone
            controller = source.controller
            if controller is not None:
                # Sacrifice Expedition Map
                sacrifice(game, controller, source)
                # Search library for a land card, put it in hand, shuffle
                library = controller.zones[Zone.LIBRARY]
                hand = controller.zones[Zone.HAND]
                land_card = None
                for card in library.get_all():
                    if CardType.LAND in getattr(card, "card_types", set()):
                        land_card = card
                        break
                if land_card is not None:
                    library.remove(land_card)
                    hand.add(land_card)
                library.shuffle()

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{2}, {T}, Sacrifice: Search for a land card.",
            ),
        ]


class WishclawTalisman(Artifact):
    """Wishclaw Talisman — {1}{B} — Enters with 3 wish counters.
    {1}, {T}, Remove counter: Tutor a card; opponent gains control."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wishclaw Talisman")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault(
            "rules_text",
            "This artifact enters with three wish counters on it.\n"
            "{1}, {T}, Remove a wish counter from this artifact: Search your library "
            "for a card, put it into your hand, then shuffle. An opponent gains "
            "control of this artifact. Activate only during your turn.",
        )
        super().__init__(**kwargs)
        self.wish_counters: int = 3

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            if source.wish_counters <= 0:
                return False
            src.is_tapped = True
            source.wish_counters -= 1
            return True

        def _effect(game: Any) -> None:
            from engine.types import Zone
            controller = source.controller
            if controller is not None:
                # Search library for a card, put it in hand, shuffle
                library = controller.zones[Zone.LIBRARY]
                hand = controller.zones[Zone.HAND]
                all_cards = library.get_all()
                if all_cards:
                    chosen = all_cards[0]  # Simplified: pick first card
                    library.remove(chosen)
                    hand.add(chosen)
                library.shuffle()
            # ENGINE LIMITATION: control transfer to opponent not implemented

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="{1}, {T}, Remove a wish counter: Tutor; opponent gains control.",
            ),
        ]


# ---------------------------------------------------------------------------
# Equipment (batch 2)
# ---------------------------------------------------------------------------

class FishingPole(Artifact):
    """Fishing Pole — {1} — Equipment with bait counter mechanics."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Fishing Pole")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "Equipped creature has \"{1}, {T}, Tap Fishing Pole: Put a bait counter "
            "on Fishing Pole.\"\nWhenever equipped creature becomes untapped, remove "
            "a bait counter from this Equipment. If you do, create a 1/1 blue Fish "
            "creature token.\nEquip {2}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None
        self.bait_counters: int = 0


class PiratesCutlass(Artifact):
    """Pirate's Cutlass — {3} — Equipment. ETB attach to Pirate.
    Equipped creature gets +2/+1. Equip {2}."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Pirate's Cutlass")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Equipment"}
        kwargs.setdefault(
            "rules_text",
            "When this Equipment enters, attach it to target Pirate you control.\n"
            "Equipped creature gets +2/+1.\nEquip {2}",
        )
        super().__init__(**kwargs)
        self.attached_to: Any | None = None


# ---------------------------------------------------------------------------
# Vehicle
# ---------------------------------------------------------------------------

class CultivatorsCaravan(Artifact):
    """Cultivator's Caravan — {3} — Vehicle 5/5. {T}: Add any color. Crew 3."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cultivator's Caravan")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Vehicle"}
        kwargs.setdefault(
            "rules_text",
            "{T}: Add one mana of any color.\nCrew 3",
        )
        super().__init__(**kwargs)
        self.base_power: int = 5
        self.base_toughness: int = 5
        self.crew_cost: int = 3

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _tap_cost(game: Any, src: Any) -> bool:
            if getattr(src, "is_tapped", False):
                return False
            src.is_tapped = True
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_tap_cost, mana_produced=_effect,
                        description="{T}: Add one mana of any color."),
        ]


# ---------------------------------------------------------------------------
# Artifact creatures
# ---------------------------------------------------------------------------

class CrystalBarricade(ArtifactCreature):
    """Crystal Barricade — {1}{W} — 0/4 Wall. Defender. You have hexproof.
    Prevent all noncombat damage to other creatures you control."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crystal Barricade")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("base_power", 0)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Wall"}
        kwargs.setdefault("keywords", Keyword.DEFENDER)
        kwargs.setdefault(
            "rules_text",
            "Defender\nYou have hexproof.\n"
            "Prevent all noncombat damage that would be dealt to other creatures you control.",
        )
        super().__init__(**kwargs)


class ScrawlingCrawler(ArtifactCreature):
    """Scrawling Crawler — {3} — 3/2 Phyrexian Construct.
    Upkeep: each player draws. Opponent draws → loses 1 life."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Scrawling Crawler")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Phyrexian", "Construct"}
        kwargs.setdefault(
            "rules_text",
            "At the beginning of your upkeep, each player draws a card.\n"
            "Whenever an opponent draws a card, that player loses 1 life.",
        )
        super().__init__(**kwargs)


class CampusGuide(ArtifactCreature):
    """Campus Guide — {2} — 2/1 Golem. ETB: search for basic land on top."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Campus Guide")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Golem"}
        kwargs.setdefault(
            "rules_text",
            "When this creature enters, you may search your library for a basic "
            "land card, reveal it, then shuffle and put that card on top.",
        )
        super().__init__(**kwargs)


class Juggernaut(ArtifactCreature):
    """Juggernaut — {4} — 5/3. Attacks each combat if able. Can't be blocked by Walls."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Juggernaut")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Juggernaut"}
        kwargs.setdefault(
            "rules_text",
            "This creature attacks each combat if able.\n"
            "This creature can't be blocked by Walls.",
        )
        super().__init__(**kwargs)
        self.must_attack = True
        self.cant_be_blocked_by_walls = True


class DarksteelColossus(ArtifactCreature):
    """Darksteel Colossus — {11} — 11/11. Trample, Indestructible.
    If would go to graveyard, shuffle into library instead."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Darksteel Colossus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{11}"))
        kwargs.setdefault("base_power", 11)
        kwargs.setdefault("base_toughness", 11)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Golem"}
        kwargs.setdefault("keywords", Keyword.TRAMPLE | Keyword.INDESTRUCTIBLE)
        kwargs.setdefault(
            "rules_text",
            "Trample, indestructible\n"
            "If Darksteel Colossus would be put into a graveyard from anywhere, "
            "reveal Darksteel Colossus and shuffle it into its owner's library instead.",
        )
        super().__init__(**kwargs)


class DiamondMare(ArtifactCreature):
    """Diamond Mare — {2} — 1/3 Horse. Choose a color; gain 1 life when you
    cast a spell of that color."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Diamond Mare")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Horse"}
        kwargs.setdefault(
            "rules_text",
            "As this creature enters, choose a color.\n"
            "Whenever you cast a spell of the chosen color, you gain 1 life.",
        )
        super().__init__(**kwargs)
        self.chosen_color: str | None = None


class GateColossus(ArtifactCreature):
    """Gate Colossus — {8} — 8/8 Construct. Affinity for Gates.
    Can't be blocked by power ≤ 2."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Gate Colossus")
        kwargs.setdefault("mana_cost", ManaCost.parse("{8}"))
        kwargs.setdefault("base_power", 8)
        kwargs.setdefault("base_toughness", 8)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Construct"}
        kwargs.setdefault(
            "rules_text",
            "Affinity for Gates\n"
            "This creature can't be blocked by creatures with power 2 or less.\n"
            "Whenever a Gate you control enters, you may put this card from your "
            "graveyard on top of your library.",
        )
        super().__init__(**kwargs)


class SteelHellkite(ArtifactCreature):
    """Steel Hellkite — {6} — 5/5 Dragon. Flying. {2}: +1/+0.
    {X}: Destroy each nonland permanent with mana value X."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Steel Hellkite")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault(
            "rules_text",
            "Flying\n"
            "{2}: This creature gets +1/+0 until end of turn.\n"
            "{X}: Destroy each nonland permanent with mana value X whose controller "
            "was dealt combat damage by this creature this turn. Activate only once each turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _pump_cost(game: Any, src: Any) -> bool:
            return True  # Mana payment not modelled

        def _pump_effect(game: Any) -> None:
            source.base_power += 1

        return [
            ActivatedAbility(
                cost=_pump_cost, effect=_pump_effect,
                description="{2}: +1/+0 until end of turn.",
            ),
        ]


class ThreeTreeMascot(ArtifactCreature):
    """Three Tree Mascot — {2} — 2/1 Shapeshifter. Changeling.
    {1}: Add one mana of any color. Once each turn."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Three Tree Mascot")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Shapeshifter"}
        kwargs.setdefault(
            "rules_text",
            "Changeling\n"
            "{1}: Add one mana of any color. Activate only once each turn.",
        )
        super().__init__(**kwargs)
        # Changeling means this is every creature type
        self.is_changeling = True

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            return True  # {1} cost not tracked

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.COLORLESS, 1)

        return [
            ManaAbility(cost=_cost, mana_produced=_effect,
                        description="{1}: Add one mana of any color."),
        ]


class AdaptiveAutomaton(ArtifactCreature):
    """Adaptive Automaton — {3} — 2/2 Construct. Choose a creature type.
    Is the chosen type. Other creatures of chosen type get +1/+1."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Adaptive Automaton")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Construct"}
        kwargs.setdefault(
            "rules_text",
            "As this creature enters, choose a creature type.\n"
            "This creature is the chosen type in addition to its other types.\n"
            "Other creatures you control of the chosen type get +1/+1.",
        )
        super().__init__(**kwargs)
        self.chosen_type: str | None = None


class RamosDragonEngine(ArtifactCreature):
    """Ramos, Dragon Engine — {6} — Legendary 4/4 Dragon. Flying.
    Spell cast → counters. Remove 5 counters → add WUBRG×2."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Ramos, Dragon Engine")
        kwargs.setdefault("mana_cost", ManaCost.parse("{6}"))
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault("supertypes", set())
        kwargs["supertypes"] = (kwargs.get("supertypes") or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault("subtypes", set())
        kwargs["subtypes"] = (kwargs.get("subtypes") or set()) | {"Dragon"}
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault(
            "rules_text",
            "Flying\nWhenever you cast a spell, put a +1/+1 counter on Ramos for "
            "each of that spell's colors.\nRemove five +1/+1 counters from Ramos: "
            "Add {W}{W}{U}{U}{B}{B}{R}{R}{G}{G}. Activate only once each turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            counters = getattr(source, "plus_one_counters", 0)
            if counters < 5:
                return False
            source.plus_one_counters -= 5
            return True

        def _effect(game: Any) -> None:
            controller = source.controller
            if controller is not None:
                controller.mana_pool.add(ManaType.WHITE, 2)
                controller.mana_pool.add(ManaType.BLUE, 2)
                controller.mana_pool.add(ManaType.BLACK, 2)
                controller.mana_pool.add(ManaType.RED, 2)
                controller.mana_pool.add(ManaType.GREEN, 2)

        return [
            ActivatedAbility(
                cost=_cost, effect=_effect,
                description="Remove five +1/+1 counters: Add {W}{W}{U}{U}{B}{B}{R}{R}{G}{G}.",
            ),
        ]


# ---------------------------------------------------------------------------
# Registration data & helper
# ---------------------------------------------------------------------------

_ALL_ARTIFACTS_BATCH2: list[
    tuple[str, type, str, list[str], str, str, str, str]
] = [
    # Mana rocks
    ("Gilded Lotus", GildedLotus, "{5}",
     [], "{T}: Add three mana of any one color.",
     "rare", "Artifact", "725"),
    ("Carnelian Orb of Dragonkind", CarnelianOrbOfDragonkind, "{2}{R}",
     ["R"], "{T}: Add {R}. If spent on Dragon, it gains haste.",
     "common", "Artifact", "534"),
    ("Heraldic Banner", HeraldicBanner, "{3}",
     [], "Choose a color. Creatures of that color get +1/+0. {T}: Add chosen color.",
     "uncommon", "Artifact", "254"),
    ("Pyromancer's Goggles", PyromancersGoggles, "{5}",
     [], "{T}: Add {R}. Copy red instant/sorcery.",
     "mythic", "Legendary Artifact", "677"),
    # Utility artifacts
    ("Banner of Kinship", BannerOfKinship, "{5}",
     [], "Choose type. Fellowship counters. Chosen type gets +1/+1 per counter.",
     "rare", "Artifact", "127"),
    ("Ravenous Amulet", RavenousAmulet, "{2}",
     [], "Sac creature: draw + soul counter. Sac self: drain.",
     "uncommon", "Artifact", "131"),
    ("Goblin Firebomb", GoblinFirebomb, "{1}",
     [], "Flash. {7}, {T}, Sacrifice: Destroy target permanent.",
     "common", "Artifact", "562"),
    ("Feldon's Cane", FeldonsCane, "{1}",
     [], "{T}, Exile: Shuffle graveyard into library.",
     "uncommon", "Artifact", "673"),
    ("Soul-Guide Lantern", SoulGuideLantern, "{1}",
     [], "ETB: exile graveyard card. Sac: exile opponents' graveyards or draw.",
     "uncommon", "Artifact", "680"),
    ("Sorcerous Spyglass", SorcerousSpyglass, "{2}",
     [], "As enters, choose a name. Shut off non-mana activated abilities of that name.",
     "uncommon", "Artifact", "679"),
    ("Mazemind Tome", MazemindTome, "{2}",
     [], "Page counters for scry/draw. Exile at 4+ counters, gain 4 life.",
     "rare", "Artifact — Book", "676"),
    ("Expedition Map", ExpeditionMap, "{1}",
     [], "{2}, {T}, Sacrifice: Search for a land card.",
     "common", "Artifact", "724"),
    ("Wishclaw Talisman", WishclawTalisman, "{1}{B}",
     ["B"], "3 wish counters. Remove counter: Tutor; opponent gains control.",
     "rare", "Artifact", "617"),
    # Equipment
    ("Fishing Pole", FishingPole, "{1}",
     [], "Bait counters. Fish tokens.",
     "uncommon", "Artifact — Equipment", "128"),
    ("Pirate's Cutlass", PiratesCutlass, "{3}",
     [], "ETB attach to Pirate. Equipped creature gets +2/+1. Equip {2}.",
     "common", "Artifact — Equipment", "563"),
    # Vehicle
    ("Cultivator's Caravan", CultivatorsCaravan, "{3}",
     [], "{T}: Add any color. Crew 3.",
     "rare", "Artifact — Vehicle", "670"),
    # Artifact creatures
    ("Crystal Barricade", CrystalBarricade, "{1}{W}",
     ["W"], "Defender. You have hexproof. Prevent noncombat damage to other creatures.",
     "rare", "Artifact Creature — Wall", "7"),
    ("Scrawling Crawler", ScrawlingCrawler, "{3}",
     [], "Upkeep: each player draws. Opponent draws → loses 1 life.",
     "rare", "Artifact Creature — Phyrexian Construct", "132"),
    ("Campus Guide", CampusGuide, "{2}",
     [], "ETB: search basic land on top.",
     "common", "Artifact Creature — Golem", "251"),
    ("Juggernaut", Juggernaut, "{4}",
     [], "Attacks each combat. Can't be blocked by Walls.",
     "uncommon", "Artifact Creature — Juggernaut", "255"),
    ("Darksteel Colossus", DarksteelColossus, "{11}",
     [], "Trample, indestructible. Shuffle into library instead of graveyard.",
     "mythic", "Artifact Creature — Golem", "671"),
    ("Diamond Mare", DiamondMare, "{2}",
     [], "Choose a color. Cast spell of that color → gain 1 life.",
     "uncommon", "Artifact Creature — Horse", "672"),
    ("Gate Colossus", GateColossus, "{8}",
     [], "Affinity for Gates. Can't be blocked by power ≤ 2.",
     "uncommon", "Artifact Creature — Construct", "675"),
    ("Steel Hellkite", SteelHellkite, "{6}",
     [], "Flying. {2}: +1/+0. {X}: Destroy mana value X permanents.",
     "rare", "Artifact Creature — Dragon", "681"),
    ("Three Tree Mascot", ThreeTreeMascot, "{2}",
     [], "Changeling. {1}: Add any color (once per turn).",
     "common", "Artifact Creature — Shapeshifter", "682"),
    ("Adaptive Automaton", AdaptiveAutomaton, "{3}",
     [], "Choose type. Is that type. Others of that type get +1/+1.",
     "rare", "Artifact Creature — Construct", "723"),
    ("Ramos, Dragon Engine", RamosDragonEngine, "{6}",
     [], "Flying. Spell → counters. Remove 5 → add WUBRG×2.",
     "mythic", "Legendary Artifact Creature — Dragon", "678"),
]


def register_artifacts_batch2(registry: CardRegistry) -> None:
    """Register all batch-2 artifacts with *registry*."""
    from cards.registry import CardMetadata

    for (
        card_name, impl_class, cost_str, colors, oracle_text,
        rarity, type_line, collector_number,
    ) in _ALL_ARTIFACTS_BATCH2:
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
