"""Reference test for FDN 184 — Rune-Scarred Demon (Phase F self-ETB).

"When this creature enters, search your library for a card, put it into your
hand, then shuffle." — an own-enters trigger. Before Phase F the ETB event
fired before the card registered, so the tutor was driven by a bespoke
``on_resolve`` workaround. The Phase F ordering flip makes the registered
trigger fire on the Demon's own entry, so the ``on_resolve`` self-tutor was
removed — this test proves the tutor happens **exactly once** (a double-fire
would empty a two-card library).
"""
from __future__ import annotations

from cards.fdn.fdn_184.card_impl import RuneScarredDemon
from engine.card import Creature
from engine.decisions import Decision, GameRef
from engine.intent_player import Intent
from engine.types import ManaType, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestRuneScarredDemonSelfETB:
    def test_tutor_fires_exactly_once(self) -> None:
        demon = RuneScarredDemon()
        game = create_game()
        p = game.players[0]

        library = p.zones[Zone.LIBRARY]
        wanted = Creature(name="Wanted", base_power=1, base_toughness=1, owner=p, controller=p)
        other = Creature(name="Leftover", base_power=1, base_toughness=1, owner=p, controller=p)
        for c in (wanted, other):
            library.add(c)
            c.instance_id = game.refs.instance_id(c, Zone.LIBRARY.value)

        set_board_state(
            game, 0, hand=[demon],
            mana={ManaType.BLACK: 2, ManaType.COLORLESS: 5},
        )

        p.start_intent("tutor", Intent(
            pattern=GameRef(card=frozenset({("name", "Rune-Scarred Demon")})),
            preferences=(Decision.obj(instance=wanted.instance_id),),
        ))
        try:
            cast_spell(game, 0, "Rune-Scarred Demon")
        finally:
            if "tutor" in p._intents:
                p.end_intent("tutor")

        hand = p.zones[Zone.HAND]
        # The chosen card moved to hand; the other stays in the library —
        # exactly one tutor fired (a double-fire would have taken both).
        assert hand.contains(wanted)
        assert library.contains(other)
        assert len(library.get_all()) == 1

    def test_on_resolve_no_longer_self_tutors(self) -> None:
        # The bespoke on_resolve workaround was removed; the base CardImpl
        # on_resolve is a no-op, so resolving does not tutor on its own.
        from engine.card import CardImpl

        assert RuneScarredDemon.on_resolve is CardImpl.on_resolve
