"""Compatibility shim for cards.foundations.complex_spells.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_173 = importlib.import_module("cards.fdn.173.card_impl")
Exsanguinate = _mod_173.Exsanguinate

_mod_188 = importlib.import_module("cards.fdn.188.card_impl")
Abrade = _mod_188.Abrade

_mod_192 = importlib.import_module("cards.fdn.192.card_impl")
BurstLightning = _mod_192.BurstLightning

_mod_200 = importlib.import_module("cards.fdn.200.card_impl")
GoblinSurprise = _mod_200.GoblinSurprise

_mod_207 = importlib.import_module("cards.fdn.207.card_impl")
Slagstorm = _mod_207.Slagstorm

_mod_215 = importlib.import_module("cards.fdn.215.card_impl")
Bushwhack = _mod_215.Bushwhack

_mod_224 = importlib.import_module("cards.fdn.224.card_impl")
GnarlidColony = _mod_224.GnarlidColony

_mod_509 = importlib.import_module("cards.fdn.509.card_impl")
IntoTheRoil = _mod_509.IntoTheRoil

_mod_520 = importlib.import_module("cards.fdn.520.card_impl")
DeadlyPlot = _mod_520.DeadlyPlot

_mod_568 = importlib.import_module("cards.fdn.568.card_impl")
CharmingPrince = _mod_568.CharmingPrince

_mod_583 = importlib.import_module("cards.fdn.583.card_impl")
ValorousStance = _mod_583.ValorousStance

_mod_589 = importlib.import_module("cards.fdn.589.card_impl")
FinaleOfRevelation = _mod_589.FinaleOfRevelation

_mod_643 = importlib.import_module("cards.fdn.643.card_impl")
PrimalMight = _mod_643.PrimalMight

_mod_69 = importlib.import_module("cards.fdn.69.card_impl")
SeekersFolly = _mod_69.SeekersFolly

_mod_713 = importlib.import_module("cards.fdn.713.card_impl")
GatekeeperOfMalakir = _mod_713.GatekeeperOfMalakir

_mod_99 = importlib.import_module("cards.fdn.99.card_impl")
ApothecaryStomper = _mod_99.ApothecaryStomper


def register_complex_spells(registry):
    """Register all cards from the old complex_spells module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "Abrade": "188",
        "ApothecaryStomper": "99",
        "BurstLightning": "192",
        "Bushwhack": "215",
        "CharmingPrince": "568",
        "DeadlyPlot": "520",
        "Exsanguinate": "173",
        "FinaleOfRevelation": "589",
        "GatekeeperOfMalakir": "713",
        "GnarlidColony": "224",
        "GoblinSurprise": "200",
        "IntoTheRoil": "509",
        "PrimalMight": "643",
        "SeekersFolly": "69",
        "Slagstorm": "207",
        "ValorousStance": "583",
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

__all__ = ['Abrade', 'ApothecaryStomper', 'BurstLightning', 'Bushwhack', 'CharmingPrince', 'DeadlyPlot', 'Exsanguinate', 'FinaleOfRevelation', 'GatekeeperOfMalakir', 'GnarlidColony', 'GoblinSurprise', 'IntoTheRoil', 'PrimalMight', 'SeekersFolly', 'Slagstorm', 'ValorousStance', 'register_complex_spells']
