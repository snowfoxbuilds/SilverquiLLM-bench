# Test Interface

`test_interface.py` builds a game, plays it and shows what the players can see.
It and this file are fixed: do not change them; a change to them is never used with your engine.
`test_test_interface.py` shows the interface in use.

## The engine surface it relies on

Keep these working beside the Player Query protocol; the Test Interface uses nothing else of the engine.

| Engine surface | Used for |
| --- | --- |
| `engine.game.create_game(player1, player2, start=(step, active), sides=(Side, Side))` and `engine.game.Side` | Building a starting position |
| `engine.turn.advance(game)` | Playing: the engine's one stepping entry |
| `engine.player.Player` with `answer(query)`, `on_attempt_rejected(context, answer, error)`, `on_action_ended(context)` and `confirm_declaration(query, answer, outcome)`; the context's `kind`, `actor` and `taken` | Answering questions and hearing rejections |
| `engine.queries.PlayerQuery`, `Answer`, `asks_for`, `is_action_query`, `is_declaration_query`; `engine.decisions.Decision`, `PlayerDecision`, `satisfies`, `InvalidPlayerChoiceError` | Telling questions apart and choosing among their options |
| `game.refs.physical_card(item)`: the physical card a game object, a spell on the stack or an offered option stands for (an ability option: its source permanent's card; a token: itself) | Following a handle's card or a token, and choosing it |
| The game's `shuffle(cards)`, `choose_at_random(options, n)` and `flip_coin()` | Every random event, so the test decides its result; a library is shuffled top first |
| Each player's `zones[Zone.X].get_all()` (a library bottom to top) and `life`; `game.stack.objects()` (top first) with each object's `controller`, `source`, `is_spell` and `printed`; `engine.card.printed_class`; a permanent's `is_tapped`, `is_token`, `controller` and `owner`; `game.phase`, `game.step`, `game.active_player_index`, `game.priority_player_index`, `game.is_game_over` and `game.winner` | The Player View |

A zone change makes a new object (CR 400.7), but `physical_card` still names the same card, so a handle follows it everywhere.

## Building a game

```python
from test_interface import Phase, Side, Step, card, create_game

bolt = card(BurstLightning)
game = create_game(
    Side(hand=[bolt], battlefield=[Mountain, card(Plains, tapped=True)], library=[Island, Forest]),
    Side(life=15),
    start=(Phase.PRECOMBAT_MAIN, 0),
)
```

- `start=(step, active)` opens that step — a `Step`, or a main `Phase` — of seat `active`'s turn with its priority window open. Untap and cleanup steps have no window, so a game cannot start there.
- The turn is 1 when seat 0 is active and 2 when seat 1 is, so the starting player's first draw is still skipped.
- Each zone lists cards by predefined class or by `card(cls)` handle; a library is listed top first. `mana` fills a mana pool.
- Permanents are not summoning sick, carry no counters or damage, and a planeswalker has its printed loyalty. Nothing is shuffled or drawn.
- Every placed card gets a handle; make one with `card(...)` to follow that card.

## Looking at the game

`view(game)` returns a frozen `View`:

- `v.players[i]` has `.life`, `.library` (top first), `.hand`, `.battlefield`, `.graveyard` and `.exile`; `v.stack` is top first.
- Each entry is a `Seen` with `.card` (its predefined card, face or ability class; `None` for a token), `.owner` (the seat that owns it; a stack object shows its controller), with a permanent on its controller's side, `.tapped` and `.handle` (a card's handle, a token's `Token`, or a spell copy's `SpellCopy`).
- `v.step`, `v.active`, `v.asked` (the player whose action question the game is at), `v.game_over` and `v.winner`.
- `v.where(handle)` is the `Zone` a handled card or a token is in.
- Tokens are numbered in the order they first appear on the battlefield: `token(n)` is the n-th. Tokens one effect creates are numbered in the order it creates them, seat 0's first.
- Copies of spells are numbered in the order they are put on the stack: `spell_copy(n)` is the n-th. A copy shows the class of the spell it copies.

Hand, battlefield, graveyard and exile compare without regard to order. Power, toughness, counters, damage, keywords, effects, the mana pool, targets and combat assignments are not in the view.

## Playing

`run(game, script0, script1, chance=[...], expect=view)` plays the game from one script per seat and returns the final view. The engine asks the questions; the scripts answer every one of them.

Each `Entry` answers its player's next action question — a Priority Query, or declaring attackers or blockers — and every other question that player is asked until their following one:

- `act(*preferences, choices=..., per_query=..., distinct=..., scoped=..., branches=..., view=..., note=...)` takes an action.
- `act_illegal(...)` tries an action the rules forbid; once every branch is not offered or rejected, the same question goes to the next entry.
- `pass_priority(choices=..., branches=..., view=...)` passes, or declares nothing, answering the questions that follow with its choices.

At a declaration an entry's preferences are every creature it declares, and `scoped={creature: what}` says exactly what a creature attacks or blocks, e.g. `act(wall, scoped={wall: bear})`. A scoped answer is never filled in or trimmed: when it is not offered, or the declaration would give the creature something else, the branch is withdrawn and the entry tries its next one. Every declare-attackers step asks its declaration; a declare-blockers step asks none when nothing attacks.

A preference is a Player Decision, a predefined class, a `card(...)` handle, a `token(n)`, a `spell_copy(n)` or `player(seat)`; a handle, token or spell copy chooses its own card, token or copy, or an ability of its own permanent, and `player(seat)` chooses that player also where a question offers players among objects. Each preference picks the first offered option it is satisfied by, preferences in order. A rejected answer is answered again from the entry's next branch (`branch(...)`); a branch whose action is not offered is skipped. `per_query` maps a payload object — a handle, token or class matching a card the payload names — or a predicate over the query to the preferences for the questions it matches; a branch with `distinct=True` never chooses again an object an earlier answer of the entry chose for a question from the same source. A mandatory question that offers exactly as many options as it requires is filled.

`run` compares the view with the expected one at every action question: the first is `expect` (by default the view as play begins), and each entry's `view` replaces it. Play stops when a player whose script is empty is asked and every script is empty, or when the game ends; the final view must then be the expected one. `run` raises `PlayDiverged` when:

- the view differs from the expected one;
- an `act` is not offered, or is rejected with no branch left;
- an `act_illegal` takes effect;
- a question has nothing to answer it;
- one script runs out while another still has entries, or the game ends with entries left;
- the engine takes more than five seconds between two questions.

`chance` answers every random event in order: `shuffled(*cards)` (the new order, a library top first), `chosen_at_random(*items)` and `coin(heads)`.
