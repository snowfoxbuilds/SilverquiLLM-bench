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

