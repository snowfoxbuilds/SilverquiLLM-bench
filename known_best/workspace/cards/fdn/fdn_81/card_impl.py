"""Card implementation for Chandra, Flameshaper."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import Creature, LoyaltyAbility, Planeswalker
from engine.card_queries import choose_object
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player
    from cards.registry import CardRegistry

def _is_creature_or_planeswalker(obj: Any) -> bool:
    card_types = getattr(obj, 'card_types', set())
    return CardType.CREATURE in card_types or CardType.PLANESWALKER in card_types


class ChandraFlameshaper(Planeswalker):
    """Chandra, Flameshaper — {5}{R}{R} — 6 loyalty.

    +2: Add {R}{R}{R}. Exile top three cards. May play one this turn.
    +1: Create a token copy of target creature you control (has haste,
        sacrifice at end step).
    −4: Chandra deals 8 damage divided among any number of target
        creatures and/or planeswalkers.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault('name', 'Chandra, Flameshaper')
        kwargs.setdefault('mana_cost', ManaCost.parse('{5}{R}{R}'))
        kwargs.setdefault('starting_loyalty', 6)
        kwargs.setdefault('supertypes', set())
        kwargs['supertypes'] = (kwargs.get('supertypes') or set()) | {Supertype.LEGENDARY}
        kwargs.setdefault('subtypes', set())
        kwargs['subtypes'] = (kwargs.get('subtypes') or set()) | {'Chandra'}
        kwargs.setdefault('rules_text', '+2: Add {R}{R}{R}. Exile the top three cards of your library. Choose one. You may play that card this turn.\n+1: Create a token that\'s a copy of target creature you control, except it has haste and "At the beginning of the end step, sacrifice this token."\n−4: Chandra deals 8 damage divided as you choose among any number of target creatures and/or planeswalkers.')
        super().__init__(**kwargs)

    def get_loyalty_abilities(self) -> list[LoyaltyAbility]:
        pw = self

        def _plus2(game: Any) -> None:
            """Add {R}{R}{R}. Exile top 3, may play one this turn."""
            controller = pw.controller
            if controller is None:
                return
            controller.mana_pool.add(ManaType.RED, 3)
            library = controller.zones[Zone.LIBRARY]
            exiled_cards: list[Any] = []
            for _ in range(min(3, len(library))):
                cards = library.get_all()
                if cards:
                    card = cards[-1]
                    library.remove(card)
                    exile_zone = controller.zones[Zone.EXILE]
                    exile_zone.add(card)
                    exiled_cards.append(card)
            if exiled_cards:
                chosen = choose_object(game, controller, exiled_cards, 'Choose one exiled card to play this turn', source_card=pw)
                if chosen is not None and chosen in exiled_cards:
                    chosen._playable_this_turn = True
                    chosen._playable_by = controller

        def _plus1(game: Any) -> None:
            """Create a token copy of target creature (with haste, sacrifice at end step)."""
            from engine.game import create_token
            from engine.triggers import TriggerRegistration
            target = None
            controller = pw.controller
            if target is None or controller is None:
                return
            token = Creature(name=getattr(target, 'name', 'Token'), base_power=getattr(target, 'base_power', 0), base_toughness=getattr(target, 'base_toughness', 0), subtypes=getattr(target, 'subtypes', set()).copy() if getattr(target, 'subtypes', None) else set(), keywords=getattr(target, 'keywords', Keyword(0)) | Keyword.HASTE)
            if hasattr(target, 'card_types'):
                token.card_types = set(target.card_types)
            create_token(game, controller, token)

            def _eot_condition(game: Any, event: dict) -> bool:
                return True

            def _eot_effect(game: Any) -> None:
                """Sacrifice the token at end of turn."""
                from engine.game import sacrifice
                bf = game.get_battlefield(controller)
                if bf.contains(token):
                    sacrifice(game, controller, token)
            game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_eot_condition, effect=_eot_effect, source=token, controller=controller))

        # Each activation's division, keyed by the identity of the targets it
        # chose; set while activating and read when that activation resolves.
        divisions: dict[tuple[int, ...], list[int]] = {}

        def _minus4_targeting(game: Any, source: Any, controller: Any) -> list[Any]:
            """Choose any number of target creatures and/or planeswalkers
            (rule 601.2c via 602.2b), then divide the 8 damage among them
            (601.2d): each target except the last gets a NUMBER Player Query
            for at least 1, and the last takes the forced remainder."""
            from engine.card_queries import choose_number
            from engine.protection import has_protection_from

            candidates = [
                obj
                for player in game.players
                for obj in game.get_battlefield(player).get_all()
                if _is_creature_or_planeswalker(obj) and not has_protection_from(obj, pw)
            ]
            chosen = choose_object(
                game, controller, candidates,
                'Choose any number of target creatures and/or planeswalkers',
                source_card=pw, min=0, max=min(8, len(candidates)),
            ) if candidates else []
            if chosen is None:
                targets = []
            elif isinstance(chosen, list):
                targets = chosen
            else:
                targets = [chosen]
            amounts: list[int] = []
            remaining = 8
            for i, t in enumerate(targets):
                left_after = len(targets) - i - 1
                if left_after == 0:
                    dmg = remaining
                else:
                    dmg = choose_number(game, controller, 1, remaining - left_after, f"damage to {getattr(t, 'name', 'target')} ({remaining} of 8 left to divide)", source_card=pw)
                amounts.append(dmg)
                remaining -= dmg
            divisions[tuple(map(id, targets))] = amounts
            return targets

        def _minus4(game: Any, targets: list[Any], context: Any = None) -> None:
            """Deal the 8 damage as divided at activation; a target that is no
            longer legal is dealt nothing (rule 608.2b)."""
            from engine.game import deal_damage
            from engine.stack import surviving_targets
            amounts = divisions.pop(tuple(map(id, targets)), [])
            legal = surviving_targets(game, context, targets, is_legal=_is_creature_or_planeswalker)
            for target, dmg in zip(targets, amounts):
                if any(target is t for t in legal):
                    deal_damage(game, pw, target, dmg)
        return [LoyaltyAbility(loyalty_cost=+2, effect=_plus2, description='+2: Add {R}{R}{R}. Exile top 3, choose one to play this turn.'), LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description='+1: Create a hasty token copy of target creature (sacrifice at end step).'), LoyaltyAbility(loyalty_cost=-4, effect=_minus4, targeting=_minus4_targeting, description='−4: Deal 8 damage divided among target creatures and/or planeswalkers.')]
