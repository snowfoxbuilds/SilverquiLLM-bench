"""Reference test for FDN 142 — Healer's Hawk.

Illustrative test covering **blocker declaration / blocking restrictions**.
Healer's Hawk is a 1/1 with Flying + Lifelink. The flying keyword
restricts which creatures can legally block it: per the rules, a flying
attacker can only be blocked by creatures with flying or reach. The
engine encodes this in :func:`engine.combat._can_block`.
"""

from __future__ import annotations

from cards.fdn.fdn_142.card_impl import HealersHawk
from engine.card import Creature, printed_class
from engine.types import Keyword, ManaCost


class TestHealersHawkProperties:
    """Static card data should match the FDN 142 spec."""

    def test_is_creature(self) -> None:
        assert isinstance(HealersHawk(owner=None), Creature)

    def test_name(self) -> None:
        assert printed_class(HealersHawk(owner=None)) is HealersHawk

    def test_mana_cost(self) -> None:
        assert HealersHawk(owner=None).mana_cost == ManaCost.parse("{W}")

    def test_power_toughness(self) -> None:
        card = HealersHawk(owner=None)
        assert card.base_power == 1
        assert card.base_toughness == 1

    def test_has_flying_and_lifelink(self) -> None:
        kw = HealersHawk(owner=None).keywords
        assert Keyword.FLYING in kw
        assert Keyword.LIFELINK in kw


class TestHealersHawkBlockerRules:
    """Flying restricts which creatures can legally block this attacker."""

    @staticmethod
    def _ground_creature() -> Creature:
        c = Creature(name="Ground Bear", base_power=2, base_toughness=2)
        c.keywords = Keyword(0)
        c.is_tapped = False
        return c

    @staticmethod
    def _flying_creature() -> Creature:
        c = Creature(name="Air Bear", base_power=2, base_toughness=2)
        c.keywords = Keyword.FLYING
        c.is_tapped = False
        return c

    @staticmethod
    def _reach_creature() -> Creature:
        c = Creature(name="Spider", base_power=1, base_toughness=4)
        c.keywords = Keyword.REACH
        c.is_tapped = False
        return c

    def test_ground_creature_cannot_block_flying_attacker(self) -> None:
        from engine.combat import combat_damage_step
        from test_utils import (
            declare_attackers,
            declare_blockers,
            put_on_battlefield,
            resolve_stack,
            scenario_game,
        )

        game = scenario_game()
        p1, p2 = game.players
        attacker = put_on_battlefield(game, p1, HealersHawk())
        attacker.summoning_sick = False
        blocker = put_on_battlefield(game, p2, self._ground_creature())
        blocker.is_tapped = False
        declare_attackers(game, [attacker])
        declare_blockers(game, {attacker: [blocker]}, illegal=True)
        combat_damage_step(game)
        resolve_stack(game)
        assert p2.life == 19
        assert p1.life == 21
        assert game.get_graveyard(p1).contains(attacker) is False

    def test_flying_blocker_can_block_flying_attacker(self) -> None:
        from engine.combat import combat_damage_step
        from test_utils import (
            declare_attackers,
            declare_blockers,
            put_on_battlefield,
            resolve_stack,
            scenario_game,
        )

        game = scenario_game()
        p1, p2 = game.players
        attacker = put_on_battlefield(game, p1, HealersHawk())
        attacker.summoning_sick = False
        blocker = put_on_battlefield(game, p2, self._flying_creature())
        blocker.is_tapped = False
        declare_attackers(game, [attacker])
        declare_blockers(game, {attacker: [blocker]})
        combat_damage_step(game)
        resolve_stack(game)
        assert p2.life == 20
        assert p1.life == 21
        assert game.get_graveyard(p1).contains(attacker) is True

    def test_reach_blocker_can_block_flying_attacker(self) -> None:
        from engine.combat import combat_damage_step
        from test_utils import (
            declare_attackers,
            declare_blockers,
            put_on_battlefield,
            resolve_stack,
            scenario_game,
        )

        game = scenario_game()
        p1, p2 = game.players
        attacker = put_on_battlefield(game, p1, HealersHawk())
        attacker.summoning_sick = False
        blocker = put_on_battlefield(game, p2, self._reach_creature())
        blocker.is_tapped = False
        declare_attackers(game, [attacker])
        declare_blockers(game, {attacker: [blocker]})
        combat_damage_step(game)
        resolve_stack(game)
        assert p2.life == 20
        assert p1.life == 21
        assert game.get_graveyard(p1).contains(attacker) is True

    def test_tapped_creature_cannot_block(self) -> None:
        from engine.combat import combat_damage_step
        from test_utils import (
            declare_attackers,
            declare_blockers,
            put_on_battlefield,
            resolve_stack,
            scenario_game,
        )

        game = scenario_game()
        p1, p2 = game.players
        attacker = put_on_battlefield(game, p1, HealersHawk())
        attacker.summoning_sick = False
        blocker = put_on_battlefield(game, p2, self._flying_creature())
        blocker.is_tapped = True
        declare_attackers(game, [attacker])
        declare_blockers(game, {attacker: [blocker]}, illegal=True)
        combat_damage_step(game)
        resolve_stack(game)
        assert p2.life == 19
        assert p1.life == 21
        assert game.get_graveyard(p1).contains(attacker) is False
