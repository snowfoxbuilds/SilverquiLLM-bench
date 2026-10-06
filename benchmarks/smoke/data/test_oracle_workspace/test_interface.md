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
| `engine.player.Player` with `answer(query)`, `on_attempt_rejected(context, answer, error)` and `on_action_ended(context)`; the context's `kind`, `actor` and `taken` | Answering questions and hearing rejections |
| `engine.queries.PlayerQuery`, `Answer`, `asks_for`, `is_priority_query`; `engine.decisions.Decision`, `PlayerDecision`, `satisfies`, `InvalidPlayerChoiceError` | Telling questions apart and choosing among their options |
| `game.refs.physical_card(item)`: the physical card a game object, a spell on the stack or an offered option stands for (an ability option: its source permanent's card; a token: itself) | Following a handle's card or a token, and choosing it |
| The game's `shuffle(cards)`, `choose_at_random(options, n)` and `flip_coin()` | Every random event, so the test decides its result; a library is shuffled top first |
| Each player's `zones[Zone.X].get_all()` (a library bottom to top) and `life`; `game.stack.objects()` (top first) with each object's `controller`, `source`, `is_spell` and `printed`; `engine.card.printed_class`; a permanent's `is_tapped` and `is_token`; `game.phase`, `game.step`, `game.active_player_index`, `game.priority_player_index`, `game.is_game_over` and `game.winner` | The Player View |

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
- Each entry is a `Seen` with `.card` (its predefined card, face or ability class; `None` for a token), `.owner` (the seat whose side or card it is), `.tapped` and `.handle` (a card's handle, or a token's `Token`).
- `v.step`, `v.active`, `v.asked` (the player whose action question the game is at), `v.game_over` and `v.winner`.
- `v.where(handle)` is the `Zone` a handled card or a token is in.
- Tokens are numbered in the order they first appear on the battlefield: `token(n)` is the n-th. Tokens one effect creates are numbered in the order it creates them, seat 0's first.

Hand, battlefield, graveyard and exile compare without regard to order. Power, toughness, counters, damage, keywords, effects, the mana pool, targets and combat assignments are not in the view.

## Playing

`run(game, script0, script1, chance=[...], expect=view, check_views=True)` plays the game from one script per seat and returns the final view. The engine asks the questions; the scripts answer every one of them.

Each `Entry` answers its player's next action question — a Priority Query — and every other question that player is asked until their following one:

- `act(*preferences, choices=..., per_query=..., distinct=..., branches=..., view=..., note=...)` takes an action.
- `act_illegal(...)` tries an action the rules forbid; once every branch is not offered or rejected, the same question goes to the next entry.
- `pass_priority(choices=..., branches=..., view=...)` passes, answering the questions that follow with its choices.

A preference is a Player Decision, a predefined class, a `card(...)` handle, a `token(n)` or `player(seat)`; a handle or token chooses its own card or token, or an ability of its own permanent. Each preference picks the first offered option it is satisfied by, preferences in order. A rejected answer is answered again from the entry's next branch (`branch(...)`); a branch whose action is not offered is skipped. `per_query` maps a payload object or a predicate over the query to the preferences for the questions it matches; a branch with `distinct=True` never chooses again an object an earlier answer of the entry chose for a question from the same source. A mandatory question with exactly one possible answer — one option, required — is filled, unless `distinct` rules that option out; a question that requires several options, such as an order, is always answered by the script. An empty `per_query` list declines an optional question and fills a mandatory one to its minimum, except an order or a number, which it never fills.

`run` compares the view with the expected one at every action question: the first is `expect` (by default the view as play begins), and each entry's `view` replaces it; an entry without a `view` expects nothing the view shows to change. `check_views=False` turns the comparison off, for checking the interface itself. Play stops when a player whose script is empty is asked and every script is empty, or when the game ends; the final view must then be the expected one. `run` raises `PlayDiverged` when:

- the view differs from the expected one;
- an `act` is not offered, or is rejected with no branch left;
- an `act_illegal` takes effect;
- a question has nothing to answer it;
- one script runs out while another still has entries, or the game ends with entries left;
- the engine takes more than five seconds between two questions.

`chance` answers every random event in order: `shuffled(*cards)` (the new order, a library top first), `chosen_at_random(*items)` and `coin(heads)`.
