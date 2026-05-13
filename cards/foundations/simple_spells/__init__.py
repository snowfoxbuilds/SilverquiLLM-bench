"""Compatibility shim for cards.foundations.simple_spells.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_175 = importlib.import_module("cards.fdn.175.card_impl")
HerosDownfall = _mod_175.HerosDownfall

_mod_181 = importlib.import_module("cards.fdn.181.card_impl")
Pilfer = _mod_181.Pilfer

_mod_192 = importlib.import_module("cards.fdn.192.card_impl")
BurstLightning = _mod_192.BurstLightning

_mod_223 = importlib.import_module("cards.fdn.223.card_impl")
GiantGrowth = _mod_223.GiantGrowth

_mod_505 = importlib.import_module("cards.fdn.505.card_impl")
Cancel = _mod_505.Cancel

_mod_513 = importlib.import_module("cards.fdn.513.card_impl")
QuickStudy = _mod_513.QuickStudy

_mod_517 = importlib.import_module("cards.fdn.517.card_impl")
CemeteryRecruitment = _mod_517.CemeteryRecruitment

_mod_572 = importlib.import_module("cards.fdn.572.card_impl")
Disenchant = _mod_572.Disenchant

_mod_710 = importlib.import_module("cards.fdn.710.card_impl")
Negate = _mod_710.Negate

_mod_90 = importlib.import_module("cards.fdn.90.card_impl")
IncineratingBlast = _mod_90.IncineratingBlast


def register_simple_spells(registry):
    """Register all cards from the old simple_spells module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "BurstLightning": "192",
        "Cancel": "505",
        "CemeteryRecruitment": "517",
        "Disenchant": "572",
        "GiantGrowth": "223",
        "HerosDownfall": "175",
        "IncineratingBlast": "90",
        "Negate": "710",
        "Pilfer": "181",
        "QuickStudy": "513",
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

__all__ = ['BurstLightning', 'Cancel', 'CemeteryRecruitment', 'Disenchant', 'GiantGrowth', 'HerosDownfall', 'IncineratingBlast', 'Negate', 'Pilfer', 'QuickStudy', 'register_simple_spells']
