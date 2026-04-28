# Key Decisions

Persistent across runs. Records architectural decisions, conventions, and long-lived constraints.

## PEP 561 py.typed marker placement
- **Context**: TODO spec said "Add py.typed marker in SilverquiLLM-bench/". Reviewer noted repo-root placement isn't PEP 561 compliant.
- **Decision**: Place `py.typed` inside each distributed package (`engine/py.typed`, `cards/py.typed`) and include via `[tool.setuptools.package-data]`.
- **Reasoning**: Type checkers need the marker inside the installed package, not at repo root.
- **Impact**: engine/, cards/, pyproject.toml

## Python version: requires-python >= 3.10
- **Context**: TODO specified Python >=3.11, but build environment only has Python 3.10.12.
- **Decision**: Set `requires-python = ">=3.10"` in pyproject.toml. ruff.toml target-version remains py311.
- **Reasoning**: pip install -e . fails if requires-python exceeds available Python. Pragmatic deviation.
- **Impact**: pyproject.toml

## Zone containers use identity-based matching (not equality)
- **Context**: Zones store GameObject references. Two distinct objects with same field values must not be confused.
- **Decision**: `contains()` and `remove()` use `is` (object identity), not `==` (equality).
- **Reasoning**: Game objects are references; multiple cards can share identical stats but are distinct game objects.
- **Impact**: engine/zones.py — all lookup/removal operations

## SBAs use owner's graveyard, not controller's
- **Context**: When a permanent dies, MTG rules say it goes to its owner's graveyard, not its controller's.
- **Decision**: SBA code checks `hasattr(obj, 'owner')` and uses owner's zones for graveyard destination. Falls back to controller if no owner attribute.
- **Reasoning**: Correct per MTG comprehensive rules. Owner and controller can differ (e.g., stolen creatures).
- **Impact**: engine/state_based_actions.py

## Aura is a separate subclass of Enchantment
- **Context**: SBAs check `attached_to` to detect auras. If all Enchantments have `attached_to`, non-Aura enchantments die immediately.
- **Decision**: `Aura(Enchantment)` subclass with `is_aura = True`. SBA checks `getattr(obj, 'is_aura', False)` before applying aura detachment rules.
- **Reasoning**: Clean separation between Auras and non-Aura enchantments per MTG rules.
- **Impact**: engine/card.py, engine/state_based_actions.py

## Card subclass constructors always union mandatory CardType
- **Context**: If caller passes explicit card_types, the mandatory type could be omitted.
- **Decision**: All subclass constructors union in their mandatory type (e.g., Creature always includes CardType.CREATURE).
- **Reasoning**: Prevents invalid card objects.
- engine/card.py **Impact**: all subclass constructors 


## 7. Trigger auto-registration wired into casting and SBA paths
- **Context**: TODO item 11 requires automatic trigger registration on battlefield entry and unregistration on leave.
- **Decision**: Registration hooks placed in `casting.py` (`_resolve_spell` for permanents, `play_land` for lands) and unregistration in `state_based_actions.py` (`_move_to_graveyard`). Uses `hasattr` guard for defensive compatibility with non-CardImpl objects.
- **Reasoning**: These are the concrete code paths where cards enter/leave the battlefield. Zone containers themselves (`zones.py`) are generic and shouldn't have trigger-specific logic.
- **Impact**: Future zone-transition paths (exile, bounce, etc.) will need similar hooks when implemented.

## 8. Activated ability timing: only ability-specific restrictions in activate_ability
- **Context**: Regular activated abilities in MTG can be activated at instant speed. Only loyalty abilities have sorcery-speed restrictions.
- **Decision**: `activate_ability` only enforces ability-type-specific timing (loyalty = sorcery speed). General priority checks remain in `priority_loop`, consistent with KEY_DECISIONS #5.
- **Reasoning**: Keeps timing enforcement centralized in `priority_loop` and avoids duplicating priority checks across cast_spell, activate_ability, etc.
- **Impact**: `engine/abilities.py` — regular abilities have no timing restriction; loyalty abilities enforce sorcery speed.
