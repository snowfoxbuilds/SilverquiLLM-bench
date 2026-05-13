"""Compatibility shim for cards.foundations.auras_batch2.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_156 = importlib.import_module("cards.fdn.156.card_impl")
ImprisonedInTheMoon = _mod_156.ImprisonedInTheMoon

_mod_168 = importlib.import_module("cards.fdn.168.card_impl")
WitnessProtection = _mod_168.WitnessProtection

_mod_213 = importlib.import_module("cards.fdn.213.card_impl")
BlanchwoodArmor = _mod_213.BlanchwoodArmor

_mod_26 = importlib.import_module("cards.fdn.26.card_impl")
TwinbladeBlessing = _mod_26.TwinbladeBlessing

_mod_507 = importlib.import_module("cards.fdn.507.card_impl")
EatenByPiranhas = _mod_507.EatenByPiranhas

_mod_514 = importlib.import_module("cards.fdn.514.card_impl")
StarlightSnare = _mod_514.StarlightSnare

_mod_557 = importlib.import_module("cards.fdn.557.card_impl")
NewHorizons = _mod_557.NewHorizons

_mod_565 = importlib.import_module("cards.fdn.565.card_impl")
AngelicDestiny = _mod_565.AngelicDestiny

_mod_641 = importlib.import_module("cards.fdn.641.card_impl")
OrdealOfNylea = _mod_641.OrdealOfNylea

_mod_709 = importlib.import_module("cards.fdn.709.card_impl")
Confiscate = _mod_709.Confiscate


def register_auras_batch2(registry):
    """Register all cards from the old auras_batch2 module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AngelicDestiny": "565",
        "BlanchwoodArmor": "213",
        "Confiscate": "709",
        "EatenByPiranhas": "507",
        "ImprisonedInTheMoon": "156",
        "NewHorizons": "557",
        "OrdealOfNylea": "641",
        "StarlightSnare": "514",
        "TwinbladeBlessing": "26",
        "WitnessProtection": "168",
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

__all__ = ['AngelicDestiny', 'BlanchwoodArmor', 'Confiscate', 'EatenByPiranhas', 'ImprisonedInTheMoon', 'NewHorizons', 'OrdealOfNylea', 'StarlightSnare', 'TwinbladeBlessing', 'WitnessProtection', 'register_auras_batch2']
