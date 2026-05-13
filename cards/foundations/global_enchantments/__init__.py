"""Compatibility shim for cards.foundations.global_enchantments.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_116 = importlib.import_module("cards.fdn.116.card_impl")
AnthemOfChampions = _mod_116.AnthemOfChampions

_mod_137 = importlib.import_module("cards.fdn.137.card_impl")
AuthorityOfTheConsuls = _mod_137.AuthorityOfTheConsuls

_mod_138 = importlib.import_module("cards.fdn.138.card_impl")
BanishingLight = _mod_138.BanishingLight

_mod_179 = importlib.import_module("cards.fdn.179.card_impl")
PainfulQuandary = _mod_179.PainfulQuandary

_mod_180 = importlib.import_module("cards.fdn.180.card_impl")
PhyrexianArena = _mod_180.PhyrexianArena

_mod_220 = importlib.import_module("cards.fdn.220.card_impl")
GarruksUprising = _mod_220.GarruksUprising

_mod_539 = importlib.import_module("cards.fdn.539.card_impl")
GoblinOriflamme = _mod_539.GoblinOriflamme

_mod_615 = importlib.import_module("cards.fdn.615.card_impl")
VampiricRites = _mod_615.VampiricRites

_mod_717 = importlib.import_module("cards.fdn.717.card_impl")
ImpactTremors = _mod_717.ImpactTremors

_mod_92 = importlib.import_module("cards.fdn.92.card_impl")
RiteOfTheDragoncaller = _mod_92.RiteOfTheDragoncaller


def register_global_enchantments(registry):
    """Register all cards from the old global_enchantments module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AnthemOfChampions": "116",
        "AuthorityOfTheConsuls": "137",
        "BanishingLight": "138",
        "GarruksUprising": "220",
        "GoblinOriflamme": "539",
        "ImpactTremors": "717",
        "PainfulQuandary": "179",
        "PhyrexianArena": "180",
        "RiteOfTheDragoncaller": "92",
        "VampiricRites": "615",
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

__all__ = ['AnthemOfChampions', 'AuthorityOfTheConsuls', 'BanishingLight', 'GarruksUprising', 'GoblinOriflamme', 'ImpactTremors', 'PainfulQuandary', 'PhyrexianArena', 'RiteOfTheDragoncaller', 'VampiricRites', 'register_global_enchantments']
