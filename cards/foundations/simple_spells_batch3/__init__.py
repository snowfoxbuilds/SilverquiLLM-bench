"""Compatibility shim for cards.foundations.simple_spells_batch3.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_10 = importlib.import_module("cards.fdn.10.card_impl")
DivineResilience = _mod_10.DivineResilience

_mod_105b = importlib.import_module("cards.fdn.105b.card_impl")
FellingBlow = _mod_105b.FellingBlow

_mod_13 = importlib.import_module("cards.fdn.13.card_impl")
FleetingFlight = _mod_13.FleetingFlight

_mod_143 = importlib.import_module("cards.fdn.143.card_impl")
MakeYourMove = _mod_143.MakeYourMove

_mod_148 = importlib.import_module("cards.fdn.148.card_impl")
StrokeOfMidnight = _mod_148.StrokeOfMidnight

_mod_153 = importlib.import_module("cards.fdn.153.card_impl")
EssenceScatter = _mod_153.EssenceScatter

_mod_155 = importlib.import_module("cards.fdn.155.card_impl")
FleetingDistraction = _mod_155.FleetingDistraction

_mod_162 = importlib.import_module("cards.fdn.162.card_impl")
RunAwayTogether = _mod_162.RunAwayTogether

_mod_169 = importlib.import_module("cards.fdn.169.card_impl")
BakeIntoAPie = _mod_169.BakeIntoAPie

_mod_172 = importlib.import_module("cards.fdn.172.card_impl")
EatenAlive = _mod_172.EatenAlive

_mod_174 = importlib.import_module("cards.fdn.174.card_impl")
FakeYourOwnDeath = _mod_174.FakeYourOwnDeath

_mod_187 = importlib.import_module("cards.fdn.187.card_impl")
Zombify = _mod_187.Zombify

_mod_19 = importlib.import_module("cards.fdn.19.card_impl")
JoustThrough = _mod_19.JoustThrough

_mod_20 = importlib.import_module("cards.fdn.20.card_impl")
LuminousRebuke = _mod_20.LuminousRebuke

_mod_209 = importlib.import_module("cards.fdn.209.card_impl")
SureStrike = _mod_209.SureStrike

_mod_212 = importlib.import_module("cards.fdn.212.card_impl")
BiteDown = _mod_212.BiteDown

_mod_214 = importlib.import_module("cards.fdn.214.card_impl")
BrokenWings = _mod_214.BrokenWings

_mod_233 = importlib.import_module("cards.fdn.233.card_impl")
SnakeskinVeil = _mod_233.SnakeskinVeil


def register_simple_spells_batch3(registry):
    """Register all cards from the old simple_spells_batch3 module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "BakeIntoAPie": "169",
        "BiteDown": "212",
        "BrokenWings": "214",
        "DivineResilience": "10",
        "EatenAlive": "172",
        "EssenceScatter": "153",
        "FakeYourOwnDeath": "174",
        "FellingBlow": "105b",
        "FleetingDistraction": "155",
        "FleetingFlight": "13",
        "JoustThrough": "19",
        "LuminousRebuke": "20",
        "MakeYourMove": "143",
        "RunAwayTogether": "162",
        "SnakeskinVeil": "233",
        "StrokeOfMidnight": "148",
        "SureStrike": "209",
        "Zombify": "187",
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

__all__ = ['BakeIntoAPie', 'BiteDown', 'BrokenWings', 'DivineResilience', 'EatenAlive', 'EssenceScatter', 'FakeYourOwnDeath', 'FellingBlow', 'FleetingDistraction', 'FleetingFlight', 'JoustThrough', 'LuminousRebuke', 'MakeYourMove', 'RunAwayTogether', 'SnakeskinVeil', 'StrokeOfMidnight', 'SureStrike', 'Zombify', 'register_simple_spells_batch3']
