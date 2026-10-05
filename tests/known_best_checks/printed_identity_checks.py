"""Printed identity in the Known-Best Workspace (DECISION-MODEL.md › Printed identity).

Run inside ``known_best/workspace`` by ``tests/test_known_best_printed_identity.py``:
the module imports the workspace's ``engine`` and ``cards`` packages, which the
repo suite cannot import in-process alongside other workspaces.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import engine
import pytest
from cards.loader import _defines_card
from engine.card import (
    CardImpl,
    Creature,
    Equipment,
    ManaAbility,
    printed_class,
)
from engine.card_queries import choose_mode, choose_object, query_yes_no
from engine.decisions import (
    Decision,
    IntentError,
    InvalidPlayerChoiceError,
    MalformedAttrsError,
    ProtocolError,
    Role,
    satisfies,
)
from engine.game import mint_token_copy
from engine.types import CardType, Keyword, ManaCost, ManaType, Zone
from test_utils import behavioral_game, prefer

WORKSPACE = Path(engine.__file__).resolve().parents[1]
FDN = WORKSPACE / "cards/fdn"
DESCRIPTORS = {"ActivatedAbility", "ManaAbility", "LoyaltyAbility", "Mode", "ReplacementEffect"}
# Secluded Courtyard's "choose a creature type" offers creature types, not modes.
UNPRINTED_MODE_CHOICES = {"fdn_267"}


def _card(card_id: str, attr: str):
    return getattr(importlib.import_module(f"cards.fdn.{card_id}.card_impl"), attr)


def _card_classes(module):
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if issubclass(cls, CardImpl) and _defines_card(module, cls):
            yield cls


def _call(getter, game):
    """Call a descriptor getter, passing ``game`` to those that take it."""
    return getter(game) if inspect.signature(getter).parameters else getter()


def _calls(path: Path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            yield name, node


# --- the protocol surface ---------------------------------------------------


def test_invalid_player_choice_error_is_neither_engine_nor_test_fault():
    assert issubclass(InvalidPlayerChoiceError, Exception)
    assert not issubclass(InvalidPlayerChoiceError, (ProtocolError, IntentError))


def test_printed_attr_takes_a_class_never_a_string():
    Elves = _card("fdn_227", "LlanowarElves")
    Ability = _card("fdn_227", "LlanowarElvesAbility1")
    assert dict(Decision.obj(printed=Elves).attrs) == {"printed": Elves}
    assert dict(Decision.ability(printed=Ability).attrs) == {"printed": Ability}
    assert dict(Decision.mode(printed=Ability).attrs) == {"printed": Ability}
    for make in (Decision.obj, Decision.ability, Decision.mode):
        with pytest.raises(MalformedAttrsError):
            make(printed="Llanowar Elves")


def test_printed_matches_by_class_identity():
    Elves = _card("fdn_227", "LlanowarElves")
    impostor = type("LlanowarElves", (Creature,), {})
    offered = Decision.obj(printed=Elves, zone="hand")
    assert satisfies(offered, Decision.obj(printed=Elves))
    assert not satisfies(offered, Decision.obj(printed=impostor))


def test_named_constants_stand_for_game_symbols():
    assert Decision.obj(zone=Zone.GRAVEYARD, type=CardType.ARTIFACT) == Decision.obj(
        zone="graveyard", type="artifact"
    )
    assert Decision.obj(keyword=Keyword.FIRST_STRIKE) == Decision.obj(keyword="first_strike")
    assert Decision.mana(ManaType.RED) == Decision.mana("R")
    assert Decision.player(role=Role.OPPONENT) == Decision.player(role="opponent")


# --- the engine tags its options ----------------------------------------------


def test_object_options_carry_the_card_class():
    Elves = _card("fdn_227", "LlanowarElves")
    Ooze = _card("fdn_232", "ScavengingOoze")
    game = behavioral_game()
    player = game.players[0]
    elves, ooze = Elves(owner=player), Ooze(owner=player)
    for card in (elves, ooze):
        game.get_hand(player).add(card)
    prefer(player, Decision.obj(printed=Ooze))
    assert choose_object(game, player, [elves, ooze], "choose") is ooze
    offered = player.transcript.all()[-1].options
    assert [dict(option.attrs)["printed"] for option in offered] == [Elves, Ooze]


def test_card_query_sources_carry_the_card_instance_and_class():
    Elves = _card("fdn_227", "LlanowarElves")
    Ooze = _card("fdn_232", "ScavengingOoze")
    game = behavioral_game()
    player = game.players[0]
    elves = Elves(owner=player)
    elves.controller = player
    game.get_battlefield(player).add(elves)
    prefer(player, Decision.yes())
    query_yes_no(game, player, "ok?", source_card=elves)
    (source,) = player.transcript.all()[-1].source
    attrs = dict(source.attrs)
    assert attrs["printed"] is Elves
    assert attrs["zone"] == "battlefield"
    assert attrs["instance"] == game.refs.instance_id(elves, "battlefield")

    spell = Ooze(owner=player)
    query_yes_no(game, player, "ok?", source_card=spell)
    (source,) = player.transcript.all()[-1].source
    assert dict(source.attrs)["zone"] == "stack"


def test_copies_stand_for_what_they_copy_and_generic_tokens_for_nothing():
    Elves = _card("fdn_227", "LlanowarElves")
    assert printed_class(mint_token_copy(Elves())) is Elves
    token = Creature(name="Copy")
    assert printed_class(token) is None
    token.printed_as = Elves
    assert printed_class(token) is Elves


def test_mode_options_carry_the_printed_mode():
    GoblinSurprise = _card("fdn_200", "GoblinSurprise")
    Tokens = _card("fdn_200", "GoblinSurpriseAbility3")
    game = behavioral_game()
    player = game.players[0]
    modes = GoblinSurprise().get_modes()
    prefer(player, Decision.mode(printed=Tokens))
    chosen = choose_mode(
        game, player, [m.name for m in modes], "Choose one", printed=[m.printed for m in modes]
    )
    assert chosen == modes[1].name


def test_replacement_order_options_carry_the_printed_ability():
    from engine.replacement_effects import ReplacementEffect, _choose_replacement_order

    Tokens = _card("fdn_216", "DoublingSeasonAbility1")
    Counters = _card("fdn_216", "DoublingSeasonAbility2")
    game = behavioral_game()
    player = game.players[0]
    effects = [
        ReplacementEffect(object, None, None, lambda g, e: e, printed=Tokens),
        ReplacementEffect(object, None, None, lambda g, e: e, printed=Counters),
    ]
    prefer(player, Decision.ability(printed=Counters))
    assert _choose_replacement_order(game, player, effects) is effects[1]


def test_alternative_cost_options_carry_the_printed_ability():
    from engine.casting import _choose_cost

    Edict = _card("fdn_57", "BlasphemousEdict")
    Alternative = _card("fdn_57", "BlasphemousEdictAbility1")
    game = behavioral_game()
    player = game.players[0]
    card = Edict(owner=player)
    normal, alternative = card.mana_cost, ManaCost.parse("{B}")
    prefer(player, Decision.ability(printed=Alternative))
    assert _choose_cost(game, player, card, [(0, normal), (1, alternative)]) is alternative


# --- every printed ability a query can present is tagged ---------------------


@pytest.mark.parametrize("card_id", sorted(p.parent.name for p in FDN.glob("*/card_impl.py")))
def test_descriptors_carry_their_cards_printed_ability(card_id):
    module = importlib.import_module(f"cards.fdn.{card_id}.card_impl")
    game = behavioral_game()
    for cls in _card_classes(module):
        card = cls(owner=game.players[0])
        descriptors = [
            descriptor
            for getter in ("get_activated_abilities", "get_mana_abilities",
                           "get_loyalty_abilities", "get_modes")
            if hasattr(card, getter)
            for descriptor in _call(getattr(card, getter), game)
        ]
        for descriptor in descriptors:
            printed = descriptor.printed
            assert isinstance(printed, type), (cls, descriptor.description)
            assert printed.__module__ == module.__name__, (cls, printed)
            assert printed.__name__.startswith(cls.__name__ + "Ability")
        if issubclass(cls, Equipment):
            assert cls.equip_printed is not None, cls
        if cls.alternative_costs is not CardImpl.alternative_costs:
            assert cls.alternative_cost_printed, cls


def test_every_descriptor_construction_names_its_printed_ability():
    sources = [*FDN.rglob("*.py"), *(WORKSPACE / "engine").glob("*.py")]
    missing = []
    for path in sources:
        if path.name == "tests.py":
            continue
        for name, call in _calls(path):
            needs_printed = name in DESCRIPTORS or (
                name == "choose_mode" and path.parent.name not in UNPRINTED_MODE_CHOICES
            )
            if needs_printed and not any(keyword.arg == "printed" for keyword in call.keywords):
                missing.append(f"{path.relative_to(WORKSPACE)}:{call.lineno} {name}")
    assert missing == []


TRIGGERS = {"TriggerRegistration", "register_delayed_trigger"}


def test_every_card_trigger_names_a_printed_ability_of_its_own_card():
    """A card's trigger names one of its own card's generated classes; a
    shared helper passes on the class its caller gives it."""
    wrong = []
    for path in FDN.rglob("*.py"):
        if path.name == "tests.py":
            continue
        tree = ast.parse(path.read_text())
        own = {node.name for node in tree.body if isinstance(node, ast.ClassDef) and "Ability" in node.name}
        parameters = {
            arg.arg for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) for arg in node.args.kwonlyargs + node.args.args
        }
        for name, call in _calls(path):
            if name not in TRIGGERS:
                continue
            printed = next((k.value for k in call.keywords if k.arg == "printed"), None)
            allowed = own if path.name == "card_impl.py" else parameters
            if not (isinstance(printed, ast.Name) and printed.id in allowed):
                wrong.append(f"{path.relative_to(WORKSPACE)}:{call.lineno}")
        if path.name == "card_impl.py":
            for _, call in _calls(path):
                for keyword in call.keywords:
                    if keyword.arg and keyword.arg.endswith("_printed") and not (
                        isinstance(keyword.value, ast.Name) and keyword.value.id in own
                    ):
                        wrong.append(f"{path.relative_to(WORKSPACE)}:{call.lineno} {keyword.arg}")
    assert wrong == []


def test_a_trigger_on_the_stack_carries_its_printed_ability():
    from engine.events import EntersBattlefieldTriggeredEvent

    Ranger = _card("fdn_100", "BeastKinRanger")
    printed = _card("fdn_100", "BeastKinRangerAbility2")
    game = behavioral_game()
    me = game.players[0]
    ranger = Ranger(owner=me, controller=me)
    game.get_battlefield(me).add(ranger)
    ranger.register_triggers(game)
    bear = Creature(name="Bear", owner=me, controller=me)
    game.get_battlefield(me).add(bear)
    game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(permanent=bear, controller=me))
    (trigger,) = game.stack.objects()
    assert trigger.printed is printed

def test_basic_land_mana_abilities_carry_their_printed_ability():
    from engine import basic_lands

    for land in ("Plains", "Island", "Swamp", "Mountain", "Forest"):
        (ability,) = getattr(basic_lands, land)().get_mana_abilities()
        assert isinstance(ability, ManaAbility)
        assert ability.printed is getattr(basic_lands, f"{land}Ability1")
