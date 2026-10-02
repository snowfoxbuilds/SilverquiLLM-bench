"""Selected-card interactions after temporary ability grants end."""

import pytest

from tests.test_fra_hard_interactions import run_oracle


@pytest.mark.parametrize("copier", ["uldaros", "hall"])
def test_copy_thranduil_after_supper_food_departure(copier):
    run_oracle("""
        from cards.fra.fra_159.card_impl import UldarosTheorix
        from cards.fra.fra_179.card_impl import HallofEchoes
        from cards.hob.hob_167.card_impl import ThranduiltheElvenking
        from cards.hob.hob_86.card_impl import SupperforSpiders
        from engine.card import ActivatedAbility, Creature
        from engine.decisions import Decision
        from engine.game import gain_life, sacrifice
        from engine.types import ManaCost, ManaType, Zone
        from engine.zones import move_to_zone
        from test_utils import (activate_card_ability, behavioral_game, cast_card,
                                enter_permanent, prefer, resolve_stack)

        class ElfHealer(Creature):
            def __init__(self, **kwargs):
                super().__init__(name='Elf healer', subtypes={'Elf'},
                                 mana_cost=ManaCost(generic=7),
                                 base_power=1, base_toughness=1, **kwargs)

            def get_activated_abilities(self):
                return [ActivatedAbility(
                    cost=lambda game, source: True,
                    targeting=lambda game, source, controller: [],
                    effect=lambda game, targets, context: gain_life(game, context.controller, 2),
                    description='Heal')]

        game = behavioral_game()
        owner, opponent = game.players
        original = enter_permanent(game, owner, ThranduiltheElvenking())
        sacrifice(game, owner, original)
        opponent.mana_pool.add(ManaType.BLACK, 1)
        opponent.mana_pool.add(ManaType.COLORLESS, 1)
        cast_card(game, opponent, SupperforSpiders())
        assert opponent.zones[Zone.BATTLEFIELD].contains(original)
        opponent.mana_pool.add(ManaType.COLORLESS, 2)
        activate_card_ability(game, opponent, original)
        resolve_stack(game)
        assert owner.zones[Zone.GRAVEYARD].contains(original)
        donor = ElfHealer(owner=owner)
        owner.zones[Zone.GRAVEYARD].add(donor)
        if COPY_MODE == 'uldaros':
            prefer(owner, Decision.obj(name=original.name), Decision.obj(name=original.name))
            owner.mana_pool.add(ManaType.COLORLESS, 3)
            owner.mana_pool.add(ManaType.BLUE, 1)
            owner.mana_pool.add(ManaType.BLACK, 2)
            cast_card(game, owner, UldarosTheorix())
            token = next(card for card in owner.zones[Zone.BATTLEFIELD].get_all()
                         if card.name == original.name)
            assert token.is_token
            assert owner.zones[Zone.EXILE].contains(original)
        else:
            original.controller = owner
            move_to_zone(game, original, Zone.GRAVEYARD, Zone.BATTLEFIELD)
            token = enter_permanent(game, owner, HallofEchoes())
            prefer(owner, Decision.obj(name=original.name))
            owner.mana_pool.add(ManaType.COLORLESS, 5)
            activate_card_ability(game, owner, token)
            resolve_stack(game)
            sacrifice(game, owner, original)
        assert len(token.get_activated_abilities()) == 1
        life = owner.life
        activate_card_ability(game, owner, token)
        resolve_stack(game)
        assert owner.life == life + 2
    """.replace("COPY_MODE", repr(copier)))
