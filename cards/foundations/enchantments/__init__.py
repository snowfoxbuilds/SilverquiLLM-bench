"""Compatibility shim for cards.foundations.enchantments.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_810 = importlib.import_module("cards.fdn.810.card_impl")
HolyStrength = _mod_810.HolyStrength

_mod_811 = importlib.import_module("cards.fdn.811.card_impl")
UnholyStrength = _mod_811.UnholyStrength

_mod_812 = importlib.import_module("cards.fdn.812.card_impl")
StabWound = _mod_812.StabWound

_mod_813 = importlib.import_module("cards.fdn.813.card_impl")
Arrest = _mod_813.Arrest

_mod_814 = importlib.import_module("cards.fdn.814.card_impl")
GloriousAnthem = _mod_814.GloriousAnthem

_mod_815 = importlib.import_module("cards.fdn.815.card_impl")
DictateOfHeliod = _mod_815.DictateOfHeliod

_mod_816 = importlib.import_module("cards.fdn.816.card_impl")
BraveTheSands = _mod_816.BraveTheSands

_mod_817 = importlib.import_module("cards.fdn.817.card_impl")
Levitation = _mod_817.Levitation


def register_enchantments(registry):
    """Register all cards from the old enchantments module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "Arrest": "813",
        "BraveTheSands": "816",
        "DictateOfHeliod": "815",
        "GloriousAnthem": "814",
        "HolyStrength": "810",
        "Levitation": "817",
        "StabWound": "812",
        "UnholyStrength": "811",
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

__all__ = ['Arrest', 'BraveTheSands', 'DictateOfHeliod', 'GloriousAnthem', 'HolyStrength', 'Levitation', 'StabWound', 'UnholyStrength', 'register_enchantments']
