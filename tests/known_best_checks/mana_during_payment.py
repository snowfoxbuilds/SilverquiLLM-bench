"""Pytest plugin for ``mana_payment_presentation_checks.py``: once a player has
chosen an action, the first time the engine checks whether a mana cost can be
paid it asks the payer whether to activate a mana ability, again after each
one, until they decline — as an engine may that lets players tap mana while a
cost is paid (CR 601.2g, 602.2b). The question is optional, so a script that
names no mana ability declines it.

With ``GREEDY`` set the payer instead activates every mana ability on offer,
script or not: an action an Audited Test calls illegal for want of mana must
then still be rejected, or the position left a source that could pay.

``fra-hard-v2``'s portability checks append this file to a card module and
call :func:`install`, so it must import nothing from the repository."""

import pytest

_GAMES: list = []
GREEDY = False


def _game_of(pool):
    for game in reversed(_GAMES):
        for player in game.players:
            if player.mana_pool is pool:
                return game, player
    return None, None


def _offer(game, player) -> None:
    import engine.priority as priority
    from engine.card import ManaAbility
    from engine.queries import PlayerQuery, ask

    while True:
        seat = priority._seat(game, player)
        actions = {}
        for source in priority._controlled_permanents(game, player):
            if getattr(source, "is_tapped", False):
                continue
            for index, ability in enumerate(priority.activatable_abilities(source, game)):
                if isinstance(ability, ManaAbility) and priority._may_begin_activating(game, player, source, ability):
                    decision = priority._ability_decision(game, seat, source, index, ability)
                    actions[decision] = priority._activation(game, player, source, ability)
        if not actions:
            return
        if GREEDY:
            chosen = next(iter(actions))
        else:
            answer = ask(player, PlayerQuery(
                source=(), prompt="Activate a mana ability", options=tuple(actions), min=0, max=1,
            ))
            if not answer.selected:
                return
            chosen = answer.selected[0]
        actions[chosen]()


def _patches():
    import engine.attempts as attempts
    import engine.game_state as game_state
    import engine.mana as mana

    init, can_pay = game_state.GameState.__init__, mana.ManaPool.can_pay
    offered: set = set()

    def recording_init(self, *args, **kwargs):
        init(self, *args, **kwargs)
        _GAMES.append(self)

    def offering_can_pay(self, cost, *args, **kwargs):
        context = attempts.current()
        # Only after a question of this try has been answered: not while the
        # engine builds the options of an action question.
        if context is not None and context.boundary is not None:
            key = (id(context), id(context.boundary), id(self))
            game, player = _game_of(self)
            if game is not None and key not in offered:
                offered.add(key)
                _offer(game, player)
        return can_pay(self, cost, *args, **kwargs)

    return [(game_state.GameState, "__init__", recording_init), (mana.ManaPool, "can_pay", offering_can_pay)]


def install() -> None:
    """Patch the engine for the rest of the process."""
    import engine.mana as mana

    if getattr(mana.ManaPool, "_offers_mana_abilities", False):
        return
    for owner, name, value in _patches():
        setattr(owner, name, value)
    mana.ManaPool._offers_mana_abilities = True


def offer_mana_abilities(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the engine until ``monkeypatch`` undoes it."""
    for owner, name, value in _patches():
        monkeypatch.setattr(owner, name, value)


@pytest.fixture(autouse=True)
def _mana_abilities_offered_during_payment(monkeypatch):
    offer_mana_abilities(monkeypatch)
    yield
    _GAMES.clear()
