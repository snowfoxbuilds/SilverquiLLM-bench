"""Compatibility shim for cards.foundations.simple_creatures.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_146 = importlib.import_module("cards.fdn.146.card_impl")
SavannahLions = _mod_146.SavannahLions

_mod_150 = importlib.import_module("cards.fdn.150.card_impl")
AegisTurtle = _mod_150.AegisTurtle

_mod_191 = importlib.import_module("cards.fdn.191.card_impl")
BrazenScourge = _mod_191.BrazenScourge

_mod_491 = importlib.import_module("cards.fdn.491.card_impl")
BishopsSoldier = _mod_491.BishopsSoldier

_mod_498 = importlib.import_module("cards.fdn.498.card_impl")
LeoninSkyhunter = _mod_498.LeoninSkyhunter

_mod_522 = importlib.import_module("cards.fdn.522.card_impl")
HighbornVampire = _mod_522.HighbornVampire

_mod_543 = importlib.import_module("cards.fdn.543.card_impl")
RagingRedcap = _mod_543.RagingRedcap

_mod_548 = importlib.import_module("cards.fdn.548.card_impl")
SwabGoblin = _mod_548.SwabGoblin

_mod_552 = importlib.import_module("cards.fdn.552.card_impl")
BearCub = _mod_552.BearCub

_mod_556 = importlib.import_module("cards.fdn.556.card_impl")
MagnigothSentry = _mod_556.MagnigothSentry

_mod_558 = importlib.import_module("cards.fdn.558.card_impl")
TajuruPathwarden = _mod_558.TajuruPathwarden

_mod_559 = importlib.import_module("cards.fdn.559.card_impl")
ThornwealdArcher = _mod_559.ThornwealdArcher

_mod_734 = importlib.import_module("cards.fdn.734.card_impl")
HealersHawk = _mod_734.HealersHawk

_mod_740 = importlib.import_module("cards.fdn.740.card_impl")
SerraAngel = _mod_740.SerraAngel

_mod_757 = importlib.import_module("cards.fdn.757.card_impl")
VampireNighthawk = _mod_757.VampireNighthawk

make_vanilla = _mod_146.make_vanilla


def register_simple_creatures(registry):
    """Register all cards from the old simple_creatures module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AegisTurtle": "150",
        "BearCub": "552",
        "BishopsSoldier": "491",
        "BrazenScourge": "191",
        "HealersHawk": "734",
        "HighbornVampire": "522",
        "LeoninSkyhunter": "498",
        "MagnigothSentry": "556",
        "RagingRedcap": "543",
        "SavannahLions": "146",
        "SerraAngel": "740",
        "SwabGoblin": "548",
        "TajuruPathwarden": "558",
        "ThornwealdArcher": "559",
        "VampireNighthawk": "757",
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

__all__ = ['AegisTurtle', 'BearCub', 'BishopsSoldier', 'BrazenScourge', 'HealersHawk', 'HighbornVampire', 'LeoninSkyhunter', 'MagnigothSentry', 'RagingRedcap', 'SavannahLions', 'SerraAngel', 'SwabGoblin', 'TajuruPathwarden', 'ThornwealdArcher', 'VampireNighthawk', 'make_vanilla', 'register_simple_creatures']
