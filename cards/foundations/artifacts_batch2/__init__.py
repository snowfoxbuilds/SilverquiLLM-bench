"""Compatibility shim for cards.foundations.artifacts_batch2.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_127 = importlib.import_module("cards.fdn.127.card_impl")
BannerOfKinship = _mod_127.BannerOfKinship

_mod_128 = importlib.import_module("cards.fdn.128.card_impl")
FishingPole = _mod_128.FishingPole

_mod_131 = importlib.import_module("cards.fdn.131.card_impl")
RavenousAmulet = _mod_131.RavenousAmulet

_mod_132 = importlib.import_module("cards.fdn.132.card_impl")
ScrawlingCrawler = _mod_132.ScrawlingCrawler

_mod_251 = importlib.import_module("cards.fdn.251.card_impl")
CampusGuide = _mod_251.CampusGuide

_mod_254 = importlib.import_module("cards.fdn.254.card_impl")
HeraldicBanner = _mod_254.HeraldicBanner

_mod_255 = importlib.import_module("cards.fdn.255.card_impl")
Juggernaut = _mod_255.Juggernaut

_mod_534 = importlib.import_module("cards.fdn.534.card_impl")
CarnelianOrbOfDragonkind = _mod_534.CarnelianOrbOfDragonkind

_mod_562 = importlib.import_module("cards.fdn.562.card_impl")
GoblinFirebomb = _mod_562.GoblinFirebomb

_mod_563 = importlib.import_module("cards.fdn.563.card_impl")
PiratesCutlass = _mod_563.PiratesCutlass

_mod_617 = importlib.import_module("cards.fdn.617.card_impl")
WishclawTalisman = _mod_617.WishclawTalisman

_mod_670 = importlib.import_module("cards.fdn.670.card_impl")
CultivatorsCaravan = _mod_670.CultivatorsCaravan

_mod_671 = importlib.import_module("cards.fdn.671.card_impl")
DarksteelColossus = _mod_671.DarksteelColossus

_mod_672 = importlib.import_module("cards.fdn.672.card_impl")
DiamondMare = _mod_672.DiamondMare

_mod_673 = importlib.import_module("cards.fdn.673.card_impl")
FeldonsCane = _mod_673.FeldonsCane

_mod_675 = importlib.import_module("cards.fdn.675.card_impl")
GateColossus = _mod_675.GateColossus

_mod_676 = importlib.import_module("cards.fdn.676.card_impl")
MazemindTome = _mod_676.MazemindTome

_mod_677 = importlib.import_module("cards.fdn.677.card_impl")
PyromancersGoggles = _mod_677.PyromancersGoggles

_mod_678 = importlib.import_module("cards.fdn.678.card_impl")
RamosDragonEngine = _mod_678.RamosDragonEngine

_mod_679 = importlib.import_module("cards.fdn.679.card_impl")
SorcerousSpyglass = _mod_679.SorcerousSpyglass

_mod_680 = importlib.import_module("cards.fdn.680.card_impl")
SoulGuideLantern = _mod_680.SoulGuideLantern

_mod_681 = importlib.import_module("cards.fdn.681.card_impl")
SteelHellkite = _mod_681.SteelHellkite

_mod_682 = importlib.import_module("cards.fdn.682.card_impl")
ThreeTreeMascot = _mod_682.ThreeTreeMascot

_mod_723 = importlib.import_module("cards.fdn.723.card_impl")
AdaptiveAutomaton = _mod_723.AdaptiveAutomaton

_mod_724 = importlib.import_module("cards.fdn.724.card_impl")
ExpeditionMap = _mod_724.ExpeditionMap

_mod_725 = importlib.import_module("cards.fdn.725.card_impl")
GildedLotus = _mod_725.GildedLotus

_mod_7b = importlib.import_module("cards.fdn.7b.card_impl")
CrystalBarricade = _mod_7b.CrystalBarricade


def register_artifacts_batch2(registry):
    """Register all cards from the old artifacts_batch2 module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AdaptiveAutomaton": "723",
        "BannerOfKinship": "127",
        "CampusGuide": "251",
        "CarnelianOrbOfDragonkind": "534",
        "CrystalBarricade": "7b",
        "CultivatorsCaravan": "670",
        "DarksteelColossus": "671",
        "DiamondMare": "672",
        "ExpeditionMap": "724",
        "FeldonsCane": "673",
        "FishingPole": "128",
        "GateColossus": "675",
        "GildedLotus": "725",
        "GoblinFirebomb": "562",
        "HeraldicBanner": "254",
        "Juggernaut": "255",
        "MazemindTome": "676",
        "PiratesCutlass": "563",
        "PyromancersGoggles": "677",
        "RamosDragonEngine": "678",
        "RavenousAmulet": "131",
        "ScrawlingCrawler": "132",
        "SorcerousSpyglass": "679",
        "SoulGuideLantern": "680",
        "SteelHellkite": "681",
        "ThreeTreeMascot": "682",
        "WishclawTalisman": "617",
    }
    for cls_name, cn in _collectors.items():
        spec_path = _fdn_dir / cn / "card_spec.json"
        if not spec_path.exists():
            continue
        with open(spec_path) as f:
            spec = json.load(f)
        impl_cls = getattr(importlib.import_module(f"cards.fdn.{cn}.card_impl"), cls_name)
        # Try to extract power/toughness/keywords/colors from class instance
        _power = spec.get("power")
        _toughness = spec.get("toughness")
        _keywords = spec.get("keywords", [])
        _colors = spec.get("colors", [])
        if issubclass(impl_cls, _CardImpl):
            try:
                _inst = impl_cls(name=spec.get("name", cls_name))
                if _power is None and hasattr(_inst, "base_power"):
                    _power = str(_inst.base_power)
                if _toughness is None and hasattr(_inst, "base_toughness"):
                    _toughness = str(_inst.base_toughness)
                if not _keywords and hasattr(_inst, "keywords"):
                    from engine.types import Keyword as _Kw
                    for kw in _Kw:
                        if _inst.keywords & kw:
                            _kw_name = kw.name.replace("_", " ").title()
                            # "First Strike" -> "First strike", etc.
                            if " " in _kw_name:
                                parts = _kw_name.split(" ")
                                _kw_name = parts[0] + " " + " ".join(p.lower() for p in parts[1:])
                            _keywords.append(_kw_name)
                if not _colors and hasattr(_inst, "mana_cost"):
                    _mc = _inst.mana_cost
                    if hasattr(_mc, "pips"):
                        _colors = [mt.value for mt in _mc.pips.keys()]
            except Exception:
                pass
        meta = CardMetadata(
            name=spec.get("name", cls_name),
            mana_cost_str=spec.get("mana_cost", ""),
            type_line=spec.get("type_line", ""),
            oracle_text=spec.get("oracle_text", ""),
            power=_power,
            toughness=_toughness,
            colors=_colors,
            keywords=_keywords,
            rarity=spec.get("rarity", ""),
            set_code=spec.get("set_code", ""),
            collector_number=spec.get("collector_number", ""),
        )
        registry.register(spec.get("name", cls_name), impl_cls, meta)

__all__ = ['AdaptiveAutomaton', 'BannerOfKinship', 'CampusGuide', 'CarnelianOrbOfDragonkind', 'CrystalBarricade', 'CultivatorsCaravan', 'DarksteelColossus', 'DiamondMare', 'ExpeditionMap', 'FeldonsCane', 'FishingPole', 'GateColossus', 'GildedLotus', 'GoblinFirebomb', 'HeraldicBanner', 'Juggernaut', 'MazemindTome', 'PiratesCutlass', 'PyromancersGoggles', 'RamosDragonEngine', 'RavenousAmulet', 'ScrawlingCrawler', 'SorcerousSpyglass', 'SoulGuideLantern', 'SteelHellkite', 'ThreeTreeMascot', 'WishclawTalisman', 'register_artifacts_batch2']
