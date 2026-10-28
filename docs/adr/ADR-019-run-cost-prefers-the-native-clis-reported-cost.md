Status: ACCEPTED; its Run Cost rule and cross-check are replaced by ADR-021
Date: 2026-10-13

# ADR-019: A Run's Cost Prefers the Native CLI's Reported Cost

## Context

A run's cost was the bench's Estimated Cost alone, priced from its own versioned model-price table.
A model the table lacks then has no cost at all, and pricing rules the table does not model, such as a model whose rate rises above a context threshold, would have to be reproduced by hand for every model.
Claude Code already reports an API-equivalent USD figure for each request it makes, which the bench captured only as a cross-check; on the fra-hard-v2 Opus and Sonnet runs it equals the table's estimate on every request the table prices fully, and is complete where the table cannot price a compaction's cache writes.

## Decision

Each run records the native CLI's own figure as its Reported Cost, per request and in total, beside the Estimated Cost, which is still computed and recorded in full.
A run's Run Cost, the figure the bench shows and sums, is its Reported Cost whenever that is at least as complete as its Estimated Cost, and its Estimated Cost otherwise.
The Reported Cost takes the run's observation reasons, version qualification included, but none of the price table's; a Reported Cost that differs from a complete Estimated Cost stays as complete as it was and adds the warning `reported_cost_disagrees_with_estimate`.
Only a valid figure from the CLI is a Reported Cost: a run whose requests all lack one has none, never a zero.
Codex reports no cost, so a Codex run's Run Cost is its Estimated Cost.

## Consequences

- **Positive**: a model the table cannot price, or prices only by a rule the table lacks, still has a cost, and Claude runs need no hand-maintained price for each new model.
- **Positive**: the Estimated Cost remains a reproducible, independent check on every figure the CLI reports.
- **Negative**: the Run Cost of a Claude run rests on a figure the workload's own process produces, which a candidate could in principle steer; only the disagreement warning, version qualification, and the recorded Estimated Cost guard it. The warning never demotes the Reported Cost: a price-table gap, such as a changed list price or a long-context tier the table lacks, would otherwise demote the figure the decision trusts.
- **Neutral**: Claude and Codex runs take their cost from different sources, so a comparison across providers compares a CLI's figure with the bench's table where the two cannot be checked against each other.

## Alternatives Considered

- **Keep the table as the only source and add each model's price, with context tiers**: every model and pricing change needs a hand-entered rule before its runs have a cost, and the table already lags the CLI on cache-write splits it cannot observe.
- **Read the CLI's final `result` line instead of its per-request OTel figures**: the line is unsanitized workload stdout with one total per session, so it cannot be reconciled request by request or attributed across sessions and compactions.
- **Replace the Estimated Cost with the Reported Cost**: the bench would lose its independent check and every committed qualification proof, which records the estimate, would stop replaying.
