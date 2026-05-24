"""Card implementation for Chandra, Flameshaper."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
from benchmarks.sos.workspace.engine.card import Creature, LoyaltyAbility, Planeswalker
from benchmarks.sos.workspace.engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from benchmarks.sos.workspace.engine.events import EndStepTriggeredEvent
if TYPE_CHECKING:
    from benchmarks.sos.workspace.engine.game_state import GameState
    from benchmarks.sos.workspace.engine.player import Player
    from cards.registry import CardRegistry

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
                try:
                    chosen = controller.choose_card(exiled_cards, 'Choose one exiled card to play this turn')
                except Exception:
                    chosen = exiled_cards[0]
                if chosen is not None and chosen in exiled_cards:
                    chosen._playable_this_turn = True
                    chosen._playable_by = controller

        def _plus1(game: Any) -> None:
            """Create a token copy of target creature (with haste, sacrifice at end step)."""
            from benchmarks.sos.workspace.engine.game import create_token
            from benchmarks.sos.workspace.engine.triggers import TriggerRegistration
            target = getattr(pw, '_resolve_target', None)
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
                from benchmarks.sos.workspace.engine.game import sacrifice
                bf = game.get_battlefield(controller)
                if bf.contains(token):
                    sacrifice(game, controller, token)
            game.trigger_manager.register(TriggerRegistration(event_type=EndStepTriggeredEvent, condition=_eot_condition, effect=_eot_effect, source=token, controller=controller))

        def _minus4(game: Any) -> None:
            """Deal 8 damage divided among targets."""
            from benchmarks.sos.workspace.engine.game import deal_damage
            damage_assignments = getattr(pw, '_damage_assignments', None)
            if damage_assignments:
                for target, amount in damage_assignments:
                    deal_damage(game, pw, target, amount)
                return
            targets = getattr(pw, '_resolve_targets', None)
            if targets and len(targets) > 0:
                damage_per = 8 // len(targets)
                remainder = 8 % len(targets)
                for i, t in enumerate(targets):
                    dmg = damage_per + (1 if i < remainder else 0)
                    deal_damage(game, pw, t, dmg)
            else:
                target = getattr(pw, '_resolve_target', None)
                if target is not None:
                    deal_damage(game, pw, target, 8)
        return [LoyaltyAbility(loyalty_cost=+2, effect=_plus2, description='+2: Add {R}{R}{R}. Exile top 3, choose one to play this turn.'), LoyaltyAbility(loyalty_cost=+1, effect=_plus1, description='+1: Create a hasty token copy of target creature (sacrifice at end step).'), LoyaltyAbility(loyalty_cost=-4, effect=_minus4, description='−4: Deal 8 damage divided among target creatures and/or planeswalkers.')]
