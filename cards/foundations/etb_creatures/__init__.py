"""Compatibility shim for cards.foundations.etb_creatures.

Re-exports card classes from their new per-collector-number locations
and provides a register_* function for backward compatibility.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

_mod_104 = importlib.import_module("cards.fdn.104.card_impl")
ElvishRegrower = _mod_104.ElvishRegrower

_mod_12 = importlib.import_module("cards.fdn.12.card_impl")
FelidarSavior = _mod_12.FelidarSavior

_mod_136 = importlib.import_module("cards.fdn.136.card_impl")
AngelOfFinality = _mod_136.AngelOfFinality

_mod_14 = importlib.import_module("cards.fdn.14.card_impl")
GuardedHeir = _mod_14.GuardedHeir

_mod_144 = importlib.import_module("cards.fdn.144.card_impl")
MischievousPup = _mod_144.MischievousPup

_mod_145 = importlib.import_module("cards.fdn.145.card_impl")
ResoluteReinforcements = _mod_145.ResoluteReinforcements

_mod_16 = importlib.import_module("cards.fdn.16.card_impl")
HelpfulHunter = _mod_16.HelpfulHunter

_mod_170 = importlib.import_module("cards.fdn.170.card_impl")
BurglarRat = _mod_170.BurglarRat

_mod_21 = importlib.import_module("cards.fdn.21.card_impl")
PridefulParent = _mod_21.PridefulParent

_mod_231 = importlib.import_module("cards.fdn.231.card_impl")
ReclamationSage = _mod_231.ReclamationSage

_mod_256 = importlib.import_module("cards.fdn.256.card_impl")
MeteorGolem = _mod_256.MeteorGolem

_mod_31 = importlib.import_module("cards.fdn.31.card_impl")
BigfinBouncer = _mod_31.BigfinBouncer

_mod_42 = importlib.import_module("cards.fdn.42.card_impl")
IcewindElemental = _mod_42.IcewindElemental

_mod_496 = importlib.import_module("cards.fdn.496.card_impl")
InspiringOverseer = _mod_496.InspiringOverseer

_mod_504 = importlib.import_module("cards.fdn.504.card_impl")
BurrogBefuddler = _mod_504.BurrogBefuddler

_mod_508 = importlib.import_module("cards.fdn.508.card_impl")
ExclusionMage = _mod_508.ExclusionMage

_mod_526 = importlib.import_module("cards.fdn.526.card_impl")
SkeletonArcher = _mod_526.SkeletonArcher

_mod_532 = importlib.import_module("cards.fdn.532.card_impl")
VampireSpawn = _mod_532.VampireSpawn

_mod_544 = importlib.import_module("cards.fdn.544.card_impl")
RapaciousDragon = _mod_544.RapaciousDragon

_mod_55 = importlib.import_module("cards.fdn.55.card_impl")
ArbiterOfWoe = _mod_55.ArbiterOfWoe

_mod_579 = importlib.import_module("cards.fdn.579.card_impl")
RegalCaracal = _mod_579.RegalCaracal

_mod_596 = importlib.import_module("cards.fdn.596.card_impl")
ShipwreckDowser = _mod_596.ShipwreckDowser

_mod_634 = importlib.import_module("cards.fdn.634.card_impl")
ViashinoPyromancer = _mod_634.ViashinoPyromancer

_mod_653 = importlib.import_module("cards.fdn.653.card_impl")
Cloudblazer = _mod_653.Cloudblazer

_mod_714 = importlib.import_module("cards.fdn.714.card_impl")
MassacreWurm = _mod_714.MassacreWurm

_mod_720 = importlib.import_module("cards.fdn.720.card_impl")
PelakkaWurm = _mod_720.PelakkaWurm

_mod_75 = importlib.import_module("cards.fdn.75.card_impl")
VampireSoulcaller = _mod_75.VampireSoulcaller

_mod_84 = importlib.import_module("cards.fdn.84.card_impl")
DragonTrainer = _mod_84.DragonTrainer

_mod_98 = importlib.import_module("cards.fdn.98.card_impl")
AmbushWolf = _mod_98.AmbushWolf


def register_etb_creatures(registry):
    """Register all cards from the old etb_creatures module into *registry*."""
    from cards.registry import CardMetadata
    from engine.card import CardImpl as _CardImpl
    _fdn_dir = Path(__file__).resolve().parent.parent.parent / "fdn"
    _collectors = {
        "AmbushWolf": "98",
        "AngelOfFinality": "136",
        "ArbiterOfWoe": "55",
        "BigfinBouncer": "31",
        "BurglarRat": "170",
        "BurrogBefuddler": "504",
        "Cloudblazer": "653",
        "DragonTrainer": "84",
        "ElvishRegrower": "104",
        "ExclusionMage": "508",
        "FelidarSavior": "12",
        "GuardedHeir": "14",
        "HelpfulHunter": "16",
        "IcewindElemental": "42",
        "InspiringOverseer": "496",
        "MassacreWurm": "714",
        "MeteorGolem": "256",
        "MischievousPup": "144",
        "PelakkaWurm": "720",
        "PridefulParent": "21",
        "RapaciousDragon": "544",
        "ReclamationSage": "231",
        "RegalCaracal": "579",
        "ResoluteReinforcements": "145",
        "ShipwreckDowser": "596",
        "SkeletonArcher": "526",
        "VampireSoulcaller": "75",
        "VampireSpawn": "532",
        "ViashinoPyromancer": "634",
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

__all__ = ['AmbushWolf', 'AngelOfFinality', 'ArbiterOfWoe', 'BigfinBouncer', 'BurglarRat', 'BurrogBefuddler', 'Cloudblazer', 'DragonTrainer', 'ElvishRegrower', 'ExclusionMage', 'FelidarSavior', 'GuardedHeir', 'HelpfulHunter', 'IcewindElemental', 'InspiringOverseer', 'MassacreWurm', 'MeteorGolem', 'MischievousPup', 'PelakkaWurm', 'PridefulParent', 'RapaciousDragon', 'ReclamationSage', 'RegalCaracal', 'ResoluteReinforcements', 'ShipwreckDowser', 'SkeletonArcher', 'VampireSoulcaller', 'VampireSpawn', 'ViashinoPyromancer', 'register_etb_creatures']
