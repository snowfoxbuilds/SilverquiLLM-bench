"""Regression tests for FDN 163 — Self-Reflection.

"Create a token that's a copy of target creature you control." The token is
minted through :func:`engine.game.mint_token_copy` (rule 707.2), so it is a
distinct game object — its own ``object_id``, de-aliased characteristic
containers, and none of the original's counters/damage/tap — carrying only the
copiable characteristics. Before the engine primitive landed the impl used a
bare ``copy.copy`` that shared the original's ``object_id`` while both were live.
"""

from __future__ import annotations

from cards.fdn.fdn_163.card_impl import SelfReflection
from engine.card import Creature, Sorcery
from engine.game import add_counter
from engine.types import ManaCost
from test_utils import create_game, set_board_state


def _copy_tokens(game, player):
    return [
        o
        for o in game.get_battlefield(player).get_all()
        if getattr(o, "is_token", False)
    ]


class TestSelfReflectionProperties:
    def test_is_sorcery(self) -> None:
        assert isinstance(SelfReflection(owner=None), Sorcery)

    def test_mana_and_flashback_cost(self) -> None:
        card = SelfReflection(owner=None)
        assert card.mana_cost == ManaCost.parse("{4}{U}{U}")
        assert card.flashback_cost == ManaCost.parse("{3}{U}")


class TestSelfReflectionCopyToken:
    def _setup(self):
        game = create_game()
        p1, p2 = game.players
        bear = Creature(
            name="Grizzly Bears", base_power=2, base_toughness=2,
            subtypes={"Bear"}, owner=p1, controller=p1,
        )
        set_board_state(game, 0, battlefield=[bear])
        spell = SelfReflection(owner=p1, controller=p1)
        return game, p1, bear, spell

    def test_creates_one_token_copy(self) -> None:
        game, p1, bear, spell = self._setup()
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        tokens = _copy_tokens(game, p1)
        assert len(tokens) == 1

    def test_token_is_a_distinct_object(self) -> None:
        """The placed token differs in identity from the copied creature — the
        crux the object_id re-mint fixes (copy.copy shared the id)."""
        game, p1, bear, spell = self._setup()
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        token = _copy_tokens(game, p1)[0]
        assert token is not bear
        assert token.object_id != bear.object_id

    def test_token_carries_copiable_characteristics(self) -> None:
        """Existing behaviour preserved: the token is a functional copy."""
        game, p1, bear, spell = self._setup()
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        token = _copy_tokens(game, p1)[0]
        assert token.name == "Grizzly Bears"
        assert (token.base_power, token.base_toughness) == (2, 2)
        assert token.subtypes == {"Bear"}
        assert token.is_token is True
        assert token.controller is p1

    def test_token_containers_are_de_aliased(self) -> None:
        """Mutating the token's subtypes must not bleed into the original — a
        shallow copy shared the very same set object."""
        game, p1, bear, spell = self._setup()
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        token = _copy_tokens(game, p1)[0]
        assert token.subtypes is not bear.subtypes
        token.subtypes.add("Zombie")
        assert "Zombie" not in bear.subtypes

    def test_token_excludes_the_originals_counters(self) -> None:
        """Counters are not copiable (rule 707.2): a copy of a +1/+1-buffed
        creature is a base-P/T token, not a buffed one (the old copy.copy
        carried the counters straight over)."""
        game, p1, bear, spell = self._setup()
        add_counter(game, bear, "+1/+1", 2)
        assert bear.power == 4  # the source is a 4/4 now
        spell.chosen_targets = [bear]
        spell.on_resolve(game)
        token = _copy_tokens(game, p1)[0]
        assert token.plus_one_counters == 0
        assert token.power == 2
        assert token.toughness == 2

    def test_no_target_is_a_noop(self) -> None:
        game, p1, bear, spell = self._setup()
        spell.chosen_targets = []
        spell.on_resolve(game)
        assert _copy_tokens(game, p1) == []
