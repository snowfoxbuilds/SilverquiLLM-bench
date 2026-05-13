"""Compatibility shim for cards.foundations.activated_creatures.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_114 = importlib.import_module("cards.fdn.114.card_impl")
TreetopSnarespinner = _mod_114.TreetopSnarespinner

_mod_139 = importlib.import_module("cards.fdn.139.card_impl")
CatharCommando = _mod_139.CatharCommando

_mod_164 = importlib.import_module("cards.fdn.164.card_impl")
SpectralSailor = _mod_164.SpectralSailor

_mod_182 = importlib.import_module("cards.fdn.182.card_impl")
ReassemblingSkeleton = _mod_182.ReassemblingSkeleton

_mod_189 = importlib.import_module("cards.fdn.189.card_impl")
AxgardCavalry = _mod_189.AxgardCavalry

_mod_195 = importlib.import_module("cards.fdn.195.card_impl")
FanaticalFirebrand = _mod_195.FanaticalFirebrand

_mod_201 = importlib.import_module("cards.fdn.201.card_impl")
HeartfireImmolator = _mod_201.HeartfireImmolator

_mod_204 = importlib.import_module("cards.fdn.204.card_impl")
KrenkoMobBoss = _mod_204.KrenkoMobBoss

_mod_206 = importlib.import_module("cards.fdn.206.card_impl")
ShivanDragon = _mod_206.ShivanDragon

_mod_219b = importlib.import_module("cards.fdn.219b.card_impl")
ElvishArchdruid = _mod_219b.ElvishArchdruid

_mod_227 = importlib.import_module("cards.fdn.227.card_impl")
LlanowarElves = _mod_227.LlanowarElves

_mod_228b = importlib.import_module("cards.fdn.228b.card_impl")
MildManneredLibrarian = _mod_228b.MildManneredLibrarian

_mod_232 = importlib.import_module("cards.fdn.232.card_impl")
ScavengingOoze = _mod_232.ScavengingOoze

_mod_245 = importlib.import_module("cards.fdn.245.card_impl")
RubyDaringTracker = _mod_245.RubyDaringTracker

_mod_250 = importlib.import_module("cards.fdn.250.card_impl")
BurnishedHart = _mod_250.BurnishedHart

_mod_49 = importlib.import_module("cards.fdn.49.card_impl")
RuneSealedWall = _mod_49.RuneSealedWall

_mod_52 = importlib.import_module("cards.fdn.52.card_impl")
StrixLookout = _mod_52.StrixLookout

_mod_62 = importlib.import_module("cards.fdn.62.card_impl")
HungryGhoul = _mod_62.HungryGhoul

_mod_95 = importlib.import_module("cards.fdn.95.card_impl")
SowerOfChaos = _mod_95.SowerOfChaos


def register_activated_creatures(registry):
    """Register all cards from the old activated_creatures module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AxgardCavalry": "189",
        "BurnishedHart": "250",
        "CatharCommando": "139",
        "ElvishArchdruid": "219b",
        "FanaticalFirebrand": "195",
        "HeartfireImmolator": "201",
        "HungryGhoul": "62",
        "KrenkoMobBoss": "204",
        "LlanowarElves": "227",
        "MildManneredLibrarian": "228b",
        "ReassemblingSkeleton": "182",
        "RubyDaringTracker": "245",
        "RuneSealedWall": "49",
        "ScavengingOoze": "232",
        "ShivanDragon": "206",
        "SowerOfChaos": "95",
        "SpectralSailor": "164",
        "StrixLookout": "52",
        "TreetopSnarespinner": "114",
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

__all__ = ['AxgardCavalry', 'BurnishedHart', 'CatharCommando', 'ElvishArchdruid', 'FanaticalFirebrand', 'HeartfireImmolator', 'HungryGhoul', 'KrenkoMobBoss', 'LlanowarElves', 'MildManneredLibrarian', 'ReassemblingSkeleton', 'RubyDaringTracker', 'RuneSealedWall', 'ScavengingOoze', 'ShivanDragon', 'SowerOfChaos', 'SpectralSailor', 'StrixLookout', 'TreetopSnarespinner', 'register_activated_creatures']
