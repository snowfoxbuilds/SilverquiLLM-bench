"""Reference test for FDN 231 — Reclamation Sage.

Pattern 1 — optional ("you may") targeted ETB on a creature. The target is an
artifact or enchantment, chosen at cast via a real Player Query, captured on
the stack, and destroyed in ``on_resolve``. Because the target is optional, the
spell is castable with no legal target and the controller may decline. No dead
test backdoors — targeting flows through real engine channels.
"""

from __future__ import annotations

from cards.fdn.fdn_231.card_impl import ReclamationSage
from engine.card import Artifact, Creature, Enchantment
from engine.decisions import Decision, DecisionKind, GameRef
from engine.intent_player import Intent
from engine.types import CardType, ManaCost, ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestReclamationSageProperties:
    def test_static_data(self):
        sage = ReclamationSage(owner=None)
        assert sage.name == "Reclamation Sage"
        assert sage.mana_cost == ManaCost.parse("{2}{G}")
        assert (sage.base_power, sage.base_toughness) == (2, 1)
        assert {"Elf", "Shaman"} <= sage.subtypes


class TestReclamationSageETB:
    def _setup(self, target):
        game = create_game()
        p1, p2 = game.players
        sage = ReclamationSage(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[sage], mana={ManaType.GREEN: 3})
        set_board_state(game, 1, battlefield=[target])
        return game, p1, p2, sage, target

    def test_destroys_target_artifact(self):
        art = Artifact(name="Signet")
        game, p1, p2, sage, art = self._setup(art)
        cast_spell(game, 0, "Reclamation Sage", targets=[art])
        assert not game.get_battlefield(p2).contains(art)
        assert p2.zones[Zone.GRAVEYARD].contains(art)

    def test_destroys_target_enchantment(self):
        ench = Enchantment(name="Pacifism")
        game, p1, p2, sage, ench = self._setup(ench)
        cast_spell(game, 0, "Reclamation Sage", targets=[ench])
        assert p2.zones[Zone.GRAVEYARD].contains(ench)

    def test_option_set_only_artifacts_and_enchantments(self):
        """Legality invariant: a plain creature is never an offered target."""
        game = create_game()
        p1, p2 = game.players
        sage = ReclamationSage(owner=p1, controller=p1)
        art = Artifact(name="Signet")
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[sage], mana={ManaType.GREEN: 3})
        set_board_state(game, 1, battlefield=[art, bear])
        cast_spell(game, 0, "Reclamation Sage", targets=[art])
        obj_queries = [
            r for r in p1.transcript.all()
            if any(o.kind is DecisionKind.OBJECT for o in r.options)
        ]
        assert obj_queries, "no artifact/enchantment target query was raised"
        for record in obj_queries:
            for opt in record.options:
                if opt.kind is DecisionKind.OBJECT:
                    attrs = dict(opt.attrs)
                    assert attrs.get("name") != "Bear"

    def test_you_may_castable_with_no_legal_target(self):
        game = create_game()
        p1, p2 = game.players
        sage = ReclamationSage(owner=p1, controller=p1)
        bear = Creature(name="Bear", base_power=2, base_toughness=2)
        set_board_state(game, 0, hand=[sage], mana={ManaType.GREEN: 3})
        set_board_state(game, 1, battlefield=[bear])  # no artifact/enchantment
        cast_spell(game, 0, "Reclamation Sage")  # optional → no query, castable
        assert game.get_battlefield(p1).contains(sage)
        assert game.get_battlefield(p2).contains(bear)  # nothing destroyed

    def test_may_decline_even_with_legal_target(self):
        art = Artifact(name="Signet")
        game, p1, p2, sage, art = self._setup(art)
        p1.start_intent("decline", Intent(
            pattern=GameRef(card=frozenset({("name", "Reclamation Sage")})),
            preferences=(),
        ))
        cast_spell(game, 0, "Reclamation Sage")
        p1.end_intent("decline")
        assert game.get_battlefield(p2).contains(art)  # not destroyed
