Status: SETTLED

Last updated: 2026-05-13

# Workspace Contract

The Workspace is the only evaluatable state an Agent Container can produce. The runner stages the Workspace, mounts it at `/workspace/`, snapshots it during execution, and materializes the official evaluation Workspace as `results/{run_name}/workspace_final/`.

## Context

The benchmark now treats agents as black-box containers working in a real codebase-shaped Workspace. To keep evaluation deterministic and audit-safe, the Workspace layout is a contract. Agents may edit implementation files and engine code, but they must preserve the expected directory structure.

## Design

### Workspace layout

```plain text
/workspace/
  prompt.md
  run_manifest.json
  rulebook.md
  engine_api.md
  base_classes.py
  test_utils.md
  engine/
  cards/
    fdn/
      {card_id}/
        card_spec.json
        card_impl.py
    sos/
      {card_id}/
        card_spec.json
        card_impl.py
        tests.py        # optional, agent-written in Tested Mode
```

### Run Manifest

Immediately before container launch, the runner writes:

```json
{
  "timeout_seconds": 7200,
  "deadline_utc": "2026-05-13T22:22:00Z"
}
```

The Run Manifest is advisory runtime context only. It is not agent configuration. Mode, strategy, model selection, and prompt behavior remain baked into the Docker image.

### Card directory contract

Each card keeps its canonical implementation in:

```plain text
cards/{set}/{card_id}/card_impl.py
```

The canonical implementation class for a card must be importable from that file. The agent must not move or rename card directories.

Failure scope:

- A missing or moved `cards/sos/{card_id}/card_impl.py` is a card-level failure.
- Many moved cards fail individually.
- A missing or unreadable `cards/sos/` tree is a run-level structural failure.
- A missing or unusable `engine/` follows engine viability and snapshot fallback flow.
### FDN and SOS structure

FDN examples and SOS targets use the same directory contract.

- FDN `card_impl.py` files are filled reference implementations.
- SOS `card_impl.py` files start as templates for the agent to fill.
This keeps examples directly comparable to targets.

### Shared helpers

Shared helper files are allowed as long as each card class remains in the expected card file and folder.

Examples:

```plain text
cards/fdn/utils.py
cards/sos/utils.py
```

Avoid cross-card directory imports. Hidden dependency chains make examples harder for agents to learn from and harder for the runner to stage and evaluate.

### Writable Engine

Agents modify `/workspace/engine/` in place. There is no separate `engine_work/`.

The baseline engine remains on the host side, outside the container. After the run, the runner diffs the official evaluation Workspace's `engine/` against the host baseline engine to produce `engine_diff.patch`.

### Agent prompt rule

The prompt should state only the hard location rule:

```plain text
Each card's implementation class must remain in its assigned
cards/sos/{card_id}/card_impl.py file. Do not move or rename card directories.
```

The prompt does not need to mention shared helper files.

### Legacy Foundations layout

After FDN migration, legacy monolithic `cards/foundations/` files should not be staged into the agent Workspace. Agents should see only the per-card FDN structure and any approved set-level helpers.

The repository may keep `cards/foundations/` temporarily during migration as source material while:

1. `cards/fdn/{card_id}/card_impl.py` files are populated.
2. Registry and tests are updated.
3. Imports are verified.
4. Tests pass.
5. No `cards.foundations` imports remain.
Then delete the legacy layout.

## Decisions

- **Workspace is evaluatable state**: Evaluation reads from `results/{run_name}/workspace_final/`, not from `/output/`.
- **Run Manifest is advisory**: `/workspace/run_manifest.json` contains only `timeout_seconds` and `deadline_utc`; the runner remains the hard timeout authority.
- **No ****`engine_work/`**: Agents modify `/workspace/engine/` in place. The host baseline is used for diffs.
- **Card class location is hard contract**: Each card's canonical implementation class must be importable from `cards/{set}/{card_id}/card_impl.py`.
- **FDN and SOS share structure**: FDN examples and SOS targets use the same card directory shape.
- **Card restructuring is card-level by default**: Individual misplaced card files fail those cards; broad Workspace destruction can become run-level failure.
- **Legacy Foundations not staged**: After FDN migration, do not include monolithic `cards/foundations/` in the agent Workspace.
