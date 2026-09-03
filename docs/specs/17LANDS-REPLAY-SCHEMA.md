Status: SETTLED

Last updated: 2026-05-09

# 17lands Replay Data Schema

Schema documentation for the 17lands replay data format. This is **action-level GRE (Game Rules Engine) message data**, not the aggregate CSV. Each file contains the full game state stream for one game.

> Source: [17lands.com](http://17lands.com/) replay data export. Pre-parsed from MTGA GRE messages into clean JSON.

---

## Top-Level Structure

```json
{
  "seat_id": 1,
  "opponent_seat_id": 2,
  "events": [ ... ]
}
```

| Field | Type | Description |
| --- | --- | --- |
| `seat_id` | int | The 17lands user's seat (1 or 2) |
| `opponent_seat_id` | int | Opponent's seat |
| `events` | array | Ordered list of GRE messages (the full game stream) |

---

## Event Object

Each element in `events`:

```json
{
  "_timestamp": null,
  "type": "GREMessageType_GameStateMessage",
  "systemSeatIds": [1],
  "msgId": 4,
  "gameStateId": 1,
  "gameStateMessage": { ... }
}
```

| Field | Type | Description |
| --- | --- | --- |
| `_timestamp` | string or null | Timestamp (often null in 17lands exports) |
| `type` | string | GRE message type (see table below) |
| `systemSeatIds` | int[] | Which seats this message is visible to |
| `msgId` | int | Sequential message ID |
| `gameStateId` | int | Sequential game state version number |
| `gameStateMessage` | object | The game state payload |

**Event types observed:**

| Type | Description | Priority |
| --- | --- | --- |
| `GREMessageType_GameStateMessage` | Full or incremental game state update | 🔴 Critical |
| `GREMessageType_QueuedGameStateMessage` | Queued state update (same structure) | 🔴 Critical |

---

## GameStateMessage

The core payload. Has two modes distinguished by the `type` field:

- `GameStateType_Full` — Complete snapshot of all game state
- `GameStateType_Diff` — Incremental delta from `prevGameStateId`
```json
{
  "type": "GameStateType_Full" | "GameStateType_Diff",
  "gameStateId": 1,
  "prevGameStateId": 0,
  "gameInfo": { ... },
  "teams": [ ... ],
  "players": [ ... ],
  "turnInfo": { ... },
  "zones": [ ... ],
  "gameObjects": [ ... ],
  "annotations": [ ... ],
  "actions": [ ... ],
  "persistentAnnotations": [ ... ],
  "pendingMessageCount": 0,
  "diffDeletedInstanceIds": [ ... ],
  "diffDeletedPersistentAnnotationIds": [ ... ]
}
```

> All fields except `type` and `gameStateId` are optional in diffs. Only changed fields appear.

---

## gameInfo

Match-level metadata. Present in `GameStateType_Full` and occasionally in diffs (e.g., when `stage` changes).

```json
{
  "matchID": "2e1b340a-6bcd-492a-8ce7-c7d5a7240fe3",
  "gameNumber": 1,
  "stage": "GameStage_Start",
  "type": "GameType_Duel",
  "variant": "GameVariant_Normal",
  "matchState": "MatchState_GameInProgress",
  "matchWinCondition": "MatchWinCondition_Best2of3",
  "maxTimeoutCount": 4,
  "maxPipCount": 3,
  "timeoutDurationSec": 30,
  "superFormat": "SuperFormat_Limited",
  "mulliganType": "MulliganType_London",
  "deckConstraintInfo": {
    "minDeckSize": 40,
    "maxDeckSize": 250,
    "maxSideboardSize": 250
  }
}
```

**Key enums:**

- `stage`: `GameStage_Start` → `GameStage_Play` → `GameStage_GameOver`
- `matchState`: `MatchState_GameInProgress` → `MatchState_GameComplete` → `MatchState_MatchComplete`
---

## players

Array of player state objects. Updated in diffs when life totals or status change.

```json
{
  "lifeTotal": 20,
  "systemSeatNumber": 1,
  "status": "PlayerStatus_InGame",
  "maxHandSize": 7,
  "controllerSeatId": 1
}
```

---

## turnInfo

Current turn/phase/step. A **sibling** of `gameInfo`, not nested inside it.

```json
{
  "phase": "Phase_Main1",
  "step": "Step_Upkeep",
  "turnNumber": 3,
  "activePlayer": 2
}
```

**Phase values:** `Phase_Beginning`, `Phase_Main1`, `Phase_Combat`, `Phase_Main2`, `Phase_Ending`

**Step values:** `Step_Upkeep`, `Step_Draw`, `Step_BeginCombat`, `Step_DeclareAttack`, `Step_DeclareBlock`, `Step_CombatDamage`, `Step_EndCombat`, `Step_End`, `Step_Cleanup`

> In diffs, `turnInfo` may be empty `{}` (e.g., during mulligan phase before the game starts).

---

## zones

Array of zone state objects. In diffs, only zones that changed are included.

```json
{
  "zoneId": 31,
  "type": "ZoneType_Hand",
  "ownerSeatId": 1,
  "objectInstanceIds": [125, 124, 123, 122, 121, 120, 119]
}
```

**Zone types observed in sample:**

| Type | Per-player? | Description |
| --- | --- | --- |
| `ZoneType_Hand` | Yes | Player's hand |
| `ZoneType_Library` | Yes | Player's library (deck) |
| `ZoneType_Graveyard` | Yes | Player's graveyard |
| `ZoneType_Sideboard` | Yes | Player's sideboard |
| `ZoneType_Revealed` | Yes | Revealed cards zone |
| `ZoneType_Battlefield` | No | Shared battlefield |
| `ZoneType_Stack` | No | The stack |
| `ZoneType_Exile` | No | Exile zone |
| `ZoneType_Limbo` | No | Temporary holding zone (mid-transition) |
| `ZoneType_Command` | No | Command zone |
| `ZoneType_Suppressed` | No | Internal MTGA zone |
| `ZoneType_Pending` | No | Internal MTGA zone |

> `objectInstanceIds` is the **complete** list of objects in the zone at that state, not a delta. When a zone appears in a diff, the entire contents array replaces the previous one.

---

## gameObjects

Array of card/permanent objects. In diffs, only new or changed objects appear.

```json
{
  "instanceId": 123,
  "grpId": 102592,
  "type": "GameObjectType_Card",
  "zoneId": 31,
  "visibility": "Visibility_Private",
  "ownerSeatId": 1,
  "controllerSeatId": 1,
  "superTypes": ["SuperType_Basic"],
  "cardTypes": ["CardType_Creature"],
  "subtypes": ["SubType_Orc", "SubType_Sorcerer"],
  "color": ["CardColor_Red"],
  "power": {"value": 4},
  "toughness": {"value": 3},
  "viewers": [1],
  "name": 1111232,
  "overlayGrpId": 102592,
  "isTapped": true,
  "uniqueAbilities": [{"id": 45, "grpId": 14}]
}
```

| Field | Type | Description |
| --- | --- | --- |
| `instanceId` | int | **Unique tracking ID** for this object instance. Changes when card moves zones (see ObjectIdChanged annotation). |
| `grpId` | int | **Card identity** — maps to card name via 17lands card list. Stable across zone changes. |
| `type` | string | `GameObjectType_Card` or `GameObjectType_Ability` |
| `zoneId` | int | Which zone this object is currently in |
| `visibility` | string | `Visibility_Private` (hidden) or `Visibility_Public` (visible to all) |
| `ownerSeatId` | int | The player who owns this card |
| `controllerSeatId` | int | The player who currently controls this object |
| `superTypes` | string[] | e.g., `SuperType_Basic`, `SuperType_Legendary` |
| `cardTypes` | string[] | e.g., `CardType_Land`, `CardType_Creature`, `CardType_Instant`, `CardType_Artifact` |
| `subtypes` | string[] | e.g., `SubType_Mountain`, `SubType_Orc` |
| `color` | string[] | e.g., `CardColor_Red`, `CardColor_White` (absent for colorless) |
| `power` | `{value: int}` | Creature power (only on creatures) |
| `toughness` | `{value: int}` | Creature toughness (only on creatures) |
| `isTapped` | bool | Whether the permanent is tapped (only present when true) |
| `viewers` | int[] | Which seats can see this object (for private visibility) |
| `name` | int | **Numeric ID**, not a string name. Requires external mapping. |
| `overlayGrpId` | int | Usually same as `grpId` |
| `uniqueAbilities` | array | Abilities on this object (`id`  • `grpId`) |

**For abilities on the stack** (`GameObjectType_Ability`):

```json
{
  "instanceId": 200,
  "grpId": 88024,
  "type": "GameObjectType_Ability",
  "zoneId": 27,
  "objectSourceGrpId": 102724,
  "parentId": 199
}
```

Additional fields: `objectSourceGrpId` (source card's grpId), `parentId` (source object's instanceId).

---

## annotations

Per-state-update action records. These track what happened between the previous state and this one.

```json
{
  "id": 49,
  "affectorId": 200,
  "affectedIds": [163],
  "type": ["AnnotationType_ObjectIdChanged"],
  "details": [
    {"key": "orig_id", "type": "KeyValuePairValueType_int32", "valueInt32": [163]},
    {"key": "new_id", "type": "KeyValuePairValueType_int32", "valueInt32": [199]}
  ]
}
```

> ⚠️ `type` is always an **array** of strings, even though it's always single-element.

**Annotation types observed in sample:**

| Type | Details Keys | What It Records |
| --- | --- | --- |
| `AnnotationType_ObjectIdChanged` | `orig_id`, `new_id` | Card moved zones → got a new instanceId. This is how zone transfers are tracked. |
| `AnnotationType_ShouldntPlay` | `Reason` (string, e.g., `"EntersTapped"`) | MTGA advisor hint — card enters tapped or is suboptimal to play. |
| `AnnotationType_ColorProduction` | `colors` (int[]) | What colors a permanent can produce. Persistent annotation. |
| `AnnotationType_LinkInfo` | `LinkType` (int) | Links between objects (e.g., ability → source) |
| `AnnotationType_ObjectsSelected` | `playerId` (int) | Objects selected by a player |

**Detail value types:** Each detail entry has `key`, `type`, and a typed value field:

- `KeyValuePairValueType_int32` → `valueInt32: int[]`
- `KeyValuePairValueType_string` → `valueString: string[]`
> Full games will also include: `AnnotationType_ZoneTransfer` (with `zone_src`, `zone_dest`, `category` keys), `AnnotationType_DamageDealt`, `AnnotationType_ModifiedLife`, `AnnotationType_CounterAdded`, `AnnotationType_ResolutionComplete`.

---

## persistentAnnotations

Same structure as `annotations`, but these persist across game states (e.g., mana production info). Removed via `diffDeletedPersistentAnnotationIds`.

---

## actions

Array of available player actions at this game state. Represents what the player CAN do, not what they DID.

```json
{
  "seatId": 1,
  "action": {"instanceId": 125}
}
```

The `instanceId` references a game object the player can interact with (play a land, cast a spell, activate an ability). When a card disappears from this list between states, it was either played or is no longer legal.

---

## diffDeletedInstanceIds

Array of `instanceId` values to purge from local state tracking. Objects with these IDs no longer exist.

---

## Parsing Strategy for Replay Validation

### State Reconstruction

1. Start with the first `GameStateType_Full` message — this is the complete initial state
2. For each subsequent `GameStateType_Diff`:
  - Merge `players`, `turnInfo`, `gameInfo` (replace if present)
  - Merge `zones` — replace any zone whose `zoneId` appears in the diff
  - Merge `gameObjects` — upsert by `instanceId`
  - Process `diffDeletedInstanceIds` — remove those objects
  - Process `diffDeletedPersistentAnnotationIds` — remove those annotations
  - `annotations` are per-state (not cumulative) — they describe what just happened
### Action Extraction

Key actions are inferred from state diffs:

- **Land play**: Object moves from `ZoneType_Hand` to `ZoneType_Battlefield` via `ObjectIdChanged` annotation. New object has `CardType_Land`.
- **Spell cast**: Object appears on `ZoneType_Stack`. Later resolves to battlefield/graveyard.
- **Draw**: Object moves from `ZoneType_Library` to `ZoneType_Hand` via `ObjectIdChanged`.
- **Ability activation**: `GameObjectType_Ability` appears on `ZoneType_Stack` with `parentId` referencing the source.
- **Combat**: `turnInfo.step` transitions through `Step_DeclareAttack` → `Step_DeclareBlock` → `Step_CombatDamage`.
- **Creature death**: Object moves to `ZoneType_Graveyard`.
### Card ID Mapping

`grpId` → card name requires the 17lands card list files from [17lands.com/public_datasets](http://17lands.com/public_datasets).

---

## Sample Data

The raw JSON below shows the first ~5 turns of a Foundations limited game (Bo3). Seat 1 is the 17lands user (R/W deck), Seat 2 is the opponent (B/G deck). Opponent goes first.

**Turn 1 (Opp):** Opponent plays a fetchland (grpId 102724), activates it, fetches a Forest (102740) tapped.

**Turn 2 (User):** User draws a land (grpId 102719, enters tapped). Plays it.

**Turn 3 (Opp):** Opponent draws, plays a Swamp (102736). No attacks.

**Turn 4 (User):** User draws a Mountain (75024). Plays a Mountain. No attacks.

**Turn 5 (Opp):** Opponent draws, plays a Mountain (102738).

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-003](../adr/ADR-003-replay-validation-over-differential-testing.md) | Replay Validation Over Differential Testing |
