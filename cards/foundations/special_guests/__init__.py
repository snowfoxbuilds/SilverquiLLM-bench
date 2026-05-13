"""Compatibility shim for cards.foundations.special_guests.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_spg_74 = importlib.import_module("cards.fdn.spg_74.card_impl")
Condemn = _mod_spg_74.Condemn

_mod_spg_75 = importlib.import_module("cards.fdn.spg_75.card_impl")
SphinxsTutelage = _mod_spg_75.SphinxsTutelage

_mod_spg_76 = importlib.import_module("cards.fdn.spg_76.card_impl")
GrimTutor = _mod_spg_76.GrimTutor

_mod_spg_77 = importlib.import_module("cards.fdn.spg_77.card_impl")
Embercleave = _mod_spg_77.Embercleave

_mod_spg_78 = importlib.import_module("cards.fdn.spg_78.card_impl")
GoblinBushwhacker = _mod_spg_78.GoblinBushwhacker

_mod_spg_79 = importlib.import_module("cards.fdn.spg_79.card_impl")
BloomTender = _mod_spg_79.BloomTender

_mod_spg_80 = importlib.import_module("cards.fdn.spg_80.card_impl")
ParadiseDruid = _mod_spg_80.ParadiseDruid

_mod_spg_81 = importlib.import_module("cards.fdn.spg_81.card_impl")
AkromasMemorial = _mod_spg_81.AkromasMemorial

_mod_spg_82 = importlib.import_module("cards.fdn.spg_82.card_impl")
TemporalManipulation = _mod_spg_82.TemporalManipulation

_mod_spg_83 = importlib.import_module("cards.fdn.spg_83.card_impl")
FiendArtisan = _mod_spg_83.FiendArtisan


def register_special_guests(registry):
    """Register all cards from the old special_guests module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AkromasMemorial": "spg_81",
        "BloomTender": "spg_79",
        "Condemn": "spg_74",
        "Embercleave": "spg_77",
        "FiendArtisan": "spg_83",
        "GoblinBushwhacker": "spg_78",
        "GrimTutor": "spg_76",
        "ParadiseDruid": "spg_80",
        "SphinxsTutelage": "spg_75",
        "TemporalManipulation": "spg_82",
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

__all__ = ['AkromasMemorial', 'BloomTender', 'Condemn', 'Embercleave', 'FiendArtisan', 'GoblinBushwhacker', 'GrimTutor', 'ParadiseDruid', 'SphinxsTutelage', 'TemporalManipulation', 'register_special_guests']
