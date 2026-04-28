# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Project scaffold

### Tests
- `tests/test_scaffold.py` — Verifies pyproject.toml metadata, directory structure, importability, py.typed markers, ruff config

### Implementation
- `pyproject.toml` — Project metadata, build config, deps, pytest/mypy tool config, package-data for py.typed
- `ruff.toml` — Ruff linter configuration (line-length 100, py311 target)
- `engine/py.typed` — PEP 561 typed package marker for engine package
- `cards/py.typed` — PEP 561 typed package marker for cards package
- `.gitignore` — Added standard Python ignores (__pycache__, egg-info, ruff_cache, etc.)
- `engine/__init__.py` — Engine package init
- `cards/__init__.py` — Cards package init
- `cards/foundations/__init__.py` — Cards foundations subpackage init
- `tests/__init__.py` — Tests package init
- `tests/engine/__init__.py` — Tests engine subpackage init
- `tests/cards/__init__.py` — Tests cards subpackage init

## Item 2: Core enums and type definitions

### Tests
- `tests/engine/test_types.py` — Verifies all enums, ManaCost construction/cmc/parse, TargetRequirement

### Implementation
- `engine/types.py` — All core enums (Color, ManaType, Zone, Phase, Step, CardType, Supertype, Keyword) and dataclasses (ManaCost, TargetRequirement); revised to reject unconsumed input and negative generic mana in ManaCost.parse()

## Item 3: Zone containers

### Tests
- `tests/engine/test_zones.py` — Verifies ZoneContainer add/remove/contains/get_all/top/bottom/shuffle, Zones.new_player(), move_zone round-trip, IllegalMoveError, same-zone no-op, position=shuffle

### Implementation
- `engine/zones.py` — ZoneContainer (ordered list wrapper with add/remove/shuffle/top/bottom), Zones (per-player Zone→ZoneContainer mapping), move_zone function, IllegalMoveError exception; revised: identity-based (`is`) lookups in contains/remove, atomic position validation in move_zone

## Item 4: Player ABC and DeterministicPlayer

### Tests
- `tests/engine/test_player.py` — Verifies Player ABC cannot be instantiated, default properties, DeterministicPlayer FIFO scripted choices, ScriptExhaustedError, remaining_choices tracking

### Implementation
- `engine/player.py` — Player(ABC) with name/life/zones/mana_pool/has_lost/land_plays_remaining properties and 5 abstract methods; DeterministicPlayer with deque-based script queue; ScriptExhaustedError exception

## Item 5: Mana pool and cost payment

### Tests
- `tests/engine/test_mana.py` — Verifies ManaPool construction, add/get/total, empty, can_pay, pay (with choices & auto-pay), Player integration
- `tests/engine/test_player.py` — Updated test_mana_pool_defaults_none to expect ManaPool instance instead of None

### Implementation
- `engine/mana.py` — ManaPool class with add/empty/total/get/can_pay/pay methods, auto-pay generic logic preferring colorless; rejects negative choices; TODO: hybrid/Phyrexian comments
- `engine/player.py` — Updated Player.__init__ to initialize mana_pool as ManaPool() instead of None

## Item 6: GameState scaffold and turn structure

### Tests
- `tests/engine/test_game_state.py` — Verifies GameState construction, 2-player validation, initial state, player properties, zone accessors, phase/step advancement, mana pool clearing, run_turn loop

### Implementation
- `engine/game_state.py` — GameState class with player properties, zone accessors, advance_phase() turn progression, empty_mana_pools(); _TURN_SEQUENCE constant; rejects != 2 players
- `engine/turn.py` — run_turn() loop iterating all phases/steps of a turn; priority_loop() stub; _NO_PRIORITY_STEPS set

## Item 7: The Stack — data structure, priority passing, and resolution

### Tests
- `tests/engine/test_stack.py` — Verifies StackObject dataclass, Stack LIFO push/pop/peek/objects, priority_loop auto-pass and resolution, priority passing with DeterministicPlayer scripts, mana ability immediate resolution, check_state_based_actions stub
- `tests/engine/test_game_state.py` — Updated test_initial_stack_is_none to test_initial_stack_is_stack_instance (Stack is now initialized)

### Implementation
- `engine/stack.py` — StackObject dataclass, Stack LIFO container, priority_loop with auto-pass and stack resolution, _handle_priority helper, _get_legal_actions placeholder, check_state_based_actions stub; **revised**: priority_loop now retains priority for acting player and keeps game.priority_player_index in sync
- `engine/game_state.py` — Updated self.stack from None to Stack() instance; added Stack import
- `engine/turn.py` — Removed stub priority_loop; now imports real priority_loop from engine.stack

## Item 8: State-based actions

### Tests
- `tests/engine/test_state_based_actions.py` — 50 tests covering all 8 SBAs, check/resolve API, cascading, multi-SBA passes

### Implementation
- `engine/state_based_actions.py` — New module with check_state_based_actions (single-pass, returns bool) and resolve_state_based_actions (loop until stable); implements 8 SBAs: life<=0, toughness<=0, lethal damage, empty library draw, legend rule, token cleanup, aura validity, counter annihilation; revised: _move_to_graveyard uses obj.owner (duck-typed) for owner-based graveyard routing; token cleanup covers STACK and COMMAND zones
- `engine/stack.py` — Replaced check_state_based_actions stub with wrapper delegating to resolve_state_based_actions from the new module
- `engine/player.py` — Added drawn_from_empty_library: bool = False attribute to Player.__init__ and docstring
