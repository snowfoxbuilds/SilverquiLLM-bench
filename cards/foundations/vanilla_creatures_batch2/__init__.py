"""Compatibility shim for cards.foundations.vanilla_creatures_batch2.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_110 = importlib.import_module("cards.fdn.110.card_impl")
QuakestriderCeratops = _mod_110.QuakestriderCeratops

_mod_246 = importlib.import_module("cards.fdn.246.card_impl")
SwiftbladeVindicator = _mod_246.SwiftbladeVindicator

_mod_36 = importlib.import_module("cards.fdn.36.card_impl")
ElementalistAdept = _mod_36.ElementalistAdept

_mod_538 = importlib.import_module("cards.fdn.538.card_impl")
FireElemental = _mod_538.FireElemental

_mod_547 = importlib.import_module("cards.fdn.547.card_impl")
SkryakerGiant = _mod_547.SkryakerGiant

_mod_584 = importlib.import_module("cards.fdn.584.card_impl")
ZetalpaPrimalDawn = _mod_584.ZetalpaPrimalDawn

_mod_718 = importlib.import_module("cards.fdn.718.card_impl")
Gigantosaurus = _mod_718.Gigantosaurus


def register_vanilla_creatures_batch2(registry):
    """Register all cards from the old vanilla_creatures_batch2 module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "ElementalistAdept": "36",
        "FireElemental": "538",
        "Gigantosaurus": "718",
        "QuakestriderCeratops": "110",
        "SkryakerGiant": "547",
        "SwiftbladeVindicator": "246",
        "ZetalpaPrimalDawn": "584",
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

__all__ = ['ElementalistAdept', 'FireElemental', 'Gigantosaurus', 'QuakestriderCeratops', 'SkryakerGiant', 'SwiftbladeVindicator', 'ZetalpaPrimalDawn', 'register_vanilla_creatures_batch2']
