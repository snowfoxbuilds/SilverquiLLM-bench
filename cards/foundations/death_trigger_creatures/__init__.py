"""Compatibility shim for cards.foundations.death_trigger_creatures.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_112 = importlib.import_module("cards.fdn.112.card_impl")
SpinnerOfSouls = _mod_112.SpinnerOfSouls

_mod_120 = importlib.import_module("cards.fdn.120.card_impl")
FiendishPanda = _mod_120.FiendishPanda

_mod_235 = importlib.import_module("cards.fdn.235.card_impl")
WaryThespian = _mod_235.WaryThespian

_mod_252 = importlib.import_module("cards.fdn.252.card_impl")
GleamingBarrier = _mod_252.GleamingBarrier

_mod_257 = importlib.import_module("cards.fdn.257.card_impl")
SolemnSimulacrum = _mod_257.SolemnSimulacrum

_mod_518 = importlib.import_module("cards.fdn.518.card_impl")
CrosswayTroublemakers = _mod_518.CrosswayTroublemakers

_mod_519 = importlib.import_module("cards.fdn.519.card_impl")
CrowOfDarkTidings = _mod_519.CrowOfDarkTidings

_mod_523 = importlib.import_module("cards.fdn.523.card_impl")
MaalfeldTwins = _mod_523.MaalfeldTwins

_mod_605 = importlib.import_module("cards.fdn.605.card_impl")
DriverOfTheDead = _mod_605.DriverOfTheDead

_mod_607 = importlib.import_module("cards.fdn.607.card_impl")
KalastriaHighborn = _mod_607.KalastriaHighborn

_mod_609 = importlib.import_module("cards.fdn.609.card_impl")
MidnightReaper = _mod_609.MidnightReaper

_mod_61b = importlib.import_module("cards.fdn.61b.card_impl")
HighSocietyHunter = _mod_61b.HighSocietyHunter

_mod_63 = importlib.import_module("cards.fdn.63.card_impl")
InfernalVessel = _mod_63.InfernalVessel

_mod_64 = importlib.import_module("cards.fdn.64.card_impl")
InfestationSage = _mod_64.InfestationSage

_mod_658 = importlib.import_module("cards.fdn.658.card_impl")
GarnaBloodfistOfKeld = _mod_658.GarnaBloodfistOfKeld

_mod_66 = importlib.import_module("cards.fdn.66.card_impl")
NineLivesFamiliar = _mod_66.NineLivesFamiliar

_mod_76 = importlib.import_module("cards.fdn.76.card_impl")
VengefulBloodwitch = _mod_76.VengefulBloodwitch


def register_death_trigger_creatures(registry):
    """Register all cards from the old death_trigger_creatures module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "CrosswayTroublemakers": "518",
        "CrowOfDarkTidings": "519",
        "DriverOfTheDead": "605",
        "FiendishPanda": "120",
        "GarnaBloodfistOfKeld": "658",
        "GleamingBarrier": "252",
        "HighSocietyHunter": "61b",
        "InfernalVessel": "63",
        "InfestationSage": "64",
        "KalastriaHighborn": "607",
        "MaalfeldTwins": "523",
        "MidnightReaper": "609",
        "NineLivesFamiliar": "66",
        "SolemnSimulacrum": "257",
        "SpinnerOfSouls": "112",
        "VengefulBloodwitch": "76",
        "WaryThespian": "235",
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

__all__ = ['CrosswayTroublemakers', 'CrowOfDarkTidings', 'DriverOfTheDead', 'FiendishPanda', 'GarnaBloodfistOfKeld', 'GleamingBarrier', 'HighSocietyHunter', 'InfernalVessel', 'InfestationSage', 'KalastriaHighborn', 'MaalfeldTwins', 'MidnightReaper', 'NineLivesFamiliar', 'SolemnSimulacrum', 'SpinnerOfSouls', 'VengefulBloodwitch', 'WaryThespian', 'register_death_trigger_creatures']
