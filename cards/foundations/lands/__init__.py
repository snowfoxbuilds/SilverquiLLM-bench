"""Compatibility shim for cards.foundations.lands.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_133 = importlib.import_module("cards.fdn.133.card_impl")
SoulstoneSanctuary = _mod_133.SoulstoneSanctuary

_mod_259 = importlib.import_module("cards.fdn.259.card_impl")
BloodfellCaves = _mod_259.BloodfellCaves

_mod_260 = importlib.import_module("cards.fdn.260.card_impl")
BlossomingSands = _mod_260.BlossomingSands

_mod_261 = importlib.import_module("cards.fdn.261.card_impl")
DismalBackwater = _mod_261.DismalBackwater

_mod_262 = importlib.import_module("cards.fdn.262.card_impl")
EvolvingWilds = _mod_262.EvolvingWilds

_mod_263 = importlib.import_module("cards.fdn.263.card_impl")
JungleHollow = _mod_263.JungleHollow

_mod_264 = importlib.import_module("cards.fdn.264.card_impl")
RoguesPassage = _mod_264.RoguesPassage

_mod_265 = importlib.import_module("cards.fdn.265.card_impl")
RuggedHighlands = _mod_265.RuggedHighlands

_mod_266 = importlib.import_module("cards.fdn.266.card_impl")
ScouredBarrens = _mod_266.ScouredBarrens

_mod_268 = importlib.import_module("cards.fdn.268.card_impl")
SwiftwaterCliffs = _mod_268.SwiftwaterCliffs

_mod_269 = importlib.import_module("cards.fdn.269.card_impl")
ThornwoodFalls = _mod_269.ThornwoodFalls

_mod_270 = importlib.import_module("cards.fdn.270.card_impl")
TranquilCove = _mod_270.TranquilCove

_mod_271 = importlib.import_module("cards.fdn.271.card_impl")
WindScarredCrag = _mod_271.WindScarredCrag

from cards.fdn._land_bases import TapLand, GainLand


def register_lands(registry):
    """Register all cards from the old lands module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "BloodfellCaves": "259",
        "BlossomingSands": "260",
        "DismalBackwater": "261",
        "EvolvingWilds": "262",
        "JungleHollow": "263",
        "RoguesPassage": "264",
        "RuggedHighlands": "265",
        "ScouredBarrens": "266",
        "SoulstoneSanctuary": "133",
        "SwiftwaterCliffs": "268",
        "ThornwoodFalls": "269",
        "TranquilCove": "270",
        "WindScarredCrag": "271",
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

__all__ = ['BloodfellCaves', 'BlossomingSands', 'DismalBackwater', 'EvolvingWilds', 'GainLand', 'JungleHollow', 'RoguesPassage', 'RuggedHighlands', 'ScouredBarrens', 'SoulstoneSanctuary', 'SwiftwaterCliffs', 'TapLand', 'ThornwoodFalls', 'TranquilCove', 'WindScarredCrag', 'register_lands']
