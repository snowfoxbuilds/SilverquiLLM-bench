"""Compatibility shim for cards.foundations.artifacts.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_800 = importlib.import_module("cards.fdn.800.card_impl")
SolRing = _mod_800.SolRing

_mod_801 = importlib.import_module("cards.fdn.801.card_impl")
ArcaneSigNet = _mod_801.ArcaneSigNet

_mod_802 = importlib.import_module("cards.fdn.802.card_impl")
MindStone = _mod_802.MindStone

_mod_803 = importlib.import_module("cards.fdn.803.card_impl")
Bonesplitter = _mod_803.Bonesplitter

_mod_804 = importlib.import_module("cards.fdn.804.card_impl")
SwiftfootBoots = _mod_804.SwiftfootBoots

_mod_805 = importlib.import_module("cards.fdn.805.card_impl")
WhispersilkCloak = _mod_805.WhispersilkCloak

_mod_806 = importlib.import_module("cards.fdn.806.card_impl")
MaskOfMemory = _mod_806.MaskOfMemory

_mod_807 = importlib.import_module("cards.fdn.807.card_impl")
AltarOfTheBrood = _mod_807.AltarOfTheBrood

_mod_808 = importlib.import_module("cards.fdn.808.card_impl")
ElixirOfImmortality = _mod_808.ElixirOfImmortality

_mod_809 = importlib.import_module("cards.fdn.809.card_impl")
RelicOfProgenitus = _mod_809.RelicOfProgenitus


def register_artifacts(registry):
    """Register all cards from the old artifacts module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AltarOfTheBrood": "807",
        "ArcaneSigNet": "801",
        "Bonesplitter": "803",
        "ElixirOfImmortality": "808",
        "MaskOfMemory": "806",
        "MindStone": "802",
        "RelicOfProgenitus": "809",
        "SolRing": "800",
        "SwiftfootBoots": "804",
        "WhispersilkCloak": "805",
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

__all__ = ['AltarOfTheBrood', 'ArcaneSigNet', 'Bonesplitter', 'ElixirOfImmortality', 'MaskOfMemory', 'MindStone', 'RelicOfProgenitus', 'SolRing', 'SwiftfootBoots', 'WhispersilkCloak', 'register_artifacts']
