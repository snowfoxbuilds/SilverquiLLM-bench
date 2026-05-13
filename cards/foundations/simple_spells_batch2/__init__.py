"""Compatibility shim for cards.foundations.simple_spells_batch2.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_100 = importlib.import_module("cards.fdn.100.card_impl")
SendInThePest = _mod_100.SendInThePest

_mod_105 = importlib.import_module("cards.fdn.105.card_impl")
WitheringCurse = _mod_105.WitheringCurse

_mod_129 = importlib.import_module("cards.fdn.129.card_impl")
SeizeTheSpoils = _mod_129.SeizeTheSpoils

_mod_161 = importlib.import_module("cards.fdn.161.card_impl")
SnarlSong = _mod_161.SnarlSong

_mod_17 = importlib.import_module("cards.fdn.17.card_impl")
GroupProject = _mod_17.GroupProject

_mod_186 = importlib.import_module("cards.fdn.186.card_impl")
EmbraceTheParadox = _mod_186.EmbraceTheParadox

_mod_216 = importlib.import_module("cards.fdn.216.card_impl")
PursueThePast = _mod_216.PursueThePast

_mod_219 = importlib.import_module("cards.fdn.219.card_impl")
RapturousMoment = _mod_219.RapturousMoment

_mod_228 = importlib.import_module("cards.fdn.228.card_impl")
SocialSnub = _mod_228.SocialSnub

_mod_242 = importlib.import_module("cards.fdn.242.card_impl")
VisionarysDance = _mod_242.VisionarysDance

_mod_50 = importlib.import_module("cards.fdn.50.card_impl")
FractalAnomaly = _mod_50.FractalAnomaly

_mod_61 = importlib.import_module("cards.fdn.61.card_impl")
MusesEncouragement = _mod_61.MusesEncouragement

_mod_7 = importlib.import_module("cards.fdn.7.card_impl")
AntiquitiesOnTheLoose = _mod_7.AntiquitiesOnTheLoose

_mod_71 = importlib.import_module("cards.fdn.71.card_impl")
WisdomOfAges = _mod_71.WisdomOfAges

_mod_94 = importlib.import_module("cards.fdn.94.card_impl")
PoxPlague = _mod_94.PoxPlague


def register_simple_spells_batch2(registry):
    """Register all cards from the old simple_spells_batch2 module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AntiquitiesOnTheLoose": "7",
        "EmbraceTheParadox": "186",
        "FractalAnomaly": "50",
        "GroupProject": "17",
        "MusesEncouragement": "61",
        "PoxPlague": "94",
        "PursueThePast": "216",
        "RapturousMoment": "219",
        "SeizeTheSpoils": "129",
        "SendInThePest": "100",
        "SnarlSong": "161",
        "SocialSnub": "228",
        "VisionarysDance": "242",
        "WisdomOfAges": "71",
        "WitheringCurse": "105",
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

__all__ = ['AntiquitiesOnTheLoose', 'EmbraceTheParadox', 'FractalAnomaly', 'GroupProject', 'MusesEncouragement', 'PoxPlague', 'PursueThePast', 'RapturousMoment', 'SeizeTheSpoils', 'SendInThePest', 'SnarlSong', 'SocialSnub', 'VisionarysDance', 'WisdomOfAges', 'WitheringCurse', 'register_simple_spells_batch2']
