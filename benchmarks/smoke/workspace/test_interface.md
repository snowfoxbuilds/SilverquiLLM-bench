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
| `game.created_tokens`: every token put onto the battlefield, in creation order, departed ones included; a rollback undoes those a rejected attempt made | Numbering tokens |
| `game.created_copies`: every copy of a spell made, in creation order, resolved or countered ones included; a rollback undoes those a rejected attempt made | Numbering spell copies |
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
- A token's number, `token(n)`, is the test's label for it, not the engine's number. A view check matches each label in the expected view to a token shown in the same place and first seen at the same check — so tokens made in one window of play are labels for one another, in whatever order the engine made them, while tokens first seen at different checks never trade labels — and the label then stays on that token, even after it leaves the battlefield, across `run` calls on the same game. No other token ever passes for a labelled one: a view check fails when a label's token is not where the expected view shows it, or when the view shows a token no label holds, whatever its number. Tokens first seen together that show alike are matched in the order the engine numbered them. A token a rejected attempt made gives its label back, so a retry's token takes it.
- A spell copy's number, `spell_copy(n)`, is a label matched the same way: copies first seen together — Uldaros's copies of several cards, say — match the expected view's labels by where they show (position on the stack, or zone, class, owner and tapped status), whatever order the engine made them in, and keep their labels once they leave the stack. A copy shows the class of the spell it copies. A script naming `spell_copy(n)` before any view check has shown it names the copy the engine numbered n, unless a label already holds that copy or the label first showed in a different window than the copy, and keeps naming it. As with tokens, no other copy passes for a labelled one. A rejected attempt's copies give their labels back to the copies made on the retry.
- When a view check differs, the report shows the actual view by the engine's numbers, the labels matched so far, and the check at which each token or copy was first seen.

Hand, battlefield, graveyard and exile compare without regard to order. Power, toughness, counters, damage, keywords, effects, the mana pool, targets and combat assignments are not in the view.

## Playing

`run(game, script0, script1, chance=[...], expect=view, check_views=True)` plays the game from one script per seat and returns the final view. The engine asks the questions; the scripts answer every one of them.

Each `Entry` answers its player's next action question — a Priority Query, or declaring attackers or blockers — and every other question that player is asked until their following one:

- `act(*preferences, choices=..., per_query=..., distinct=..., scoped=..., branches=..., view=..., note=...)` takes an action.
- `act_illegal(...)` tries an action the rules forbid; once every branch is not offered or rejected, the same question goes to the next entry.
- `pass_priority(choices=..., branches=..., view=...)` passes, or declares nothing, answering the questions that follow with its choices.

At a declaration an entry's preferences are every creature it declares, and `scoped={creature: what}` says exactly what a creature attacks or blocks, e.g. `act(wall, scoped={wall: bear})`. A scoped answer is never filled in or trimmed: when it is not offered, or the declaration would give the creature something else, the branch is withdrawn and the entry tries its next one. Every declare-attackers step asks its declaration; a declare-blockers step asks none when nothing attacks.

A preference is a Player Decision, a predefined class, a `card(...)` handle, a `token(n)`, a `spell_copy(n)`, `ability(source, PrintedAbility)` or `player(seat)`; a handle, token or spell copy chooses its own card, token or copy, or an ability of its own permanent — except at an optional question other than an action question, where it never chooses one of its permanent's abilities, so naming a land as a target never taps it for mana when the engine asks, while a cost is paid, whether to activate a mana ability; `ability(source, PrintedAbility)` chooses only that printed ability of the handle's or token's permanent — say, a land's granted ability rather than the same printed ability of the card that grants it; and `player(seat)` chooses that player also where a question offers players among objects. Each preference picks the first offered option it is satisfied by, preferences in order. A rejected answer is answered again from the entry's next branch (`branch(...)`); a branch whose action is not offered is skipped. `per_query` maps a payload object — a handle, token or class matching a card the payload names — or a predicate over the query to the preferences for the questions it matches; a branch with `distinct=True` never chooses again an object an earlier answer of the entry chose for a question from the same source. Those answers belong to the entry: a rejected answer that is rolled back is forgotten, a retry of the entry keeps the rest, and every other entry — later in the script or in a later `run` — starts with none. A mandatory question with exactly one possible answer — one option, required — is filled, unless `distinct` rules that option out; a question that requires several options, such as an order, is always answered by the script. An empty `per_query` list follows the same rule: it declines an optional question, and a mandatory one diverges unless it offers only the one option it requires.

`run` compares the view with the expected one at every action question: the first is `expect` (by default the view as play begins), and each entry's `view` replaces it; an entry without a `view` expects nothing the view shows to change. `check_views=False` turns the comparison off, for checking the interface itself. Play stops when a player whose script is empty is asked and every script is empty, or when the game ends; the final view must then be the expected one. `run` raises `PlayDiverged` when:

- the view differs from the expected one;
- an `act` is not offered, or is rejected with no branch left;
- an `act_illegal` takes effect;
- a question has nothing to answer it;
- one script runs out while another still has entries, or the game ends with entries left;
- the engine takes more than five seconds between two questions.

`chance` answers every random event in order: `shuffled(*cards)` (the new order, a library top first), `chosen_at_random(*items)` and `coin(heads)`.
