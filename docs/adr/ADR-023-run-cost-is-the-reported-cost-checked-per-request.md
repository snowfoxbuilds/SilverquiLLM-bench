Status: ACCEPTED
Date: 2026-11-17

# ADR-023: A Run's Cost Is Its Reported Cost, Checked Request by Request

## Context

ADR-019 made a run's Run Cost its Reported Cost whenever that is at least as complete as its Estimated Cost; this decision supersedes it.
The Reported Cost shares only the run's observation reasons, and the Estimated Cost carries those too, so the condition always holds once the CLI gives a figure; the comparison only obscures the rule.
The Run Cost was also never recorded: the monitor derived it, and the Results Repo's measurement attribute read the Estimated Cost instead, so a run on a model the price table lacks, such as Haiku 5.5, counted as unmeasured although Claude Code priced every request.
The estimate checked the Reported Cost only as a run total, and only when the whole run was priced, so one unpriced request, such as a Haiku 5.5 subagent's beside an Opus parent's, removed the check from the whole run.

## Decision

Each run records the native CLI's own figure as its Reported Cost, per request and in total, beside the Estimated Cost, which is still computed and recorded in full.
A run's Run Cost is its Reported Cost whenever the native CLI gave one, and its Estimated Cost otherwise; each run records it as `run_cost`, with `source` `reported` or `estimated`.
The Reported Cost takes the run's observation reasons but none of the price table's; only a valid figure from the CLI is a Reported Cost, so a run whose requests all lack one has none, never a zero.
The Estimated Cost stays a second, independent figure: each request the price table prices fully is checked against the CLI's figure for it, `cost_verification` counts the requests checked, unchecked and disagreeing, and any disagreement, or a complete estimate whose total disagrees, adds the warning `reported_cost_disagrees_with_estimate`.
A Reported Cost none of whose requests could be checked adds `reported_cost_unverified`. Neither warning demotes the Reported Cost.
A model whose rates are hard to state in the table stays out of it, and its runs rely on the Reported Cost alone: Haiku 5.5 has no table entry, so its requests go unchecked.
Codex reports no cost, so a Codex run's Run Cost is its Estimated Cost.
A run served by a bench-started local model server (ADR-022) has neither: its agent reports no cost and no price applies, so its Run Cost is its Estimated Cost, missing with `model_price_unavailable`, and its `cost_verification` is null; it is never priced at zero.

## Consequences

- **Positive**: the Run Cost is a recorded field, so every reader takes the same figure, and a run whose only gap is the price table has a complete cost.
- **Positive**: a partly priced run is still checked on the requests the table prices, and the counts show how much of a Reported Cost was checked.
- **Negative**: the Run Cost of a Claude run rests on a figure the workload's own process produces, which a candidate could in principle steer; only the warnings, the OTel cross-check of every transcript request, and the recorded Estimated Cost guard it, and a model kept out of the table, such as Haiku 5.5, is never checked at all.
- **Neutral**: records written before this decision have no `run_cost`, and readers derive it with the same rule; under ADR-019's comparison that rule gives the same figure.
- **Neutral**: a local-model run's Run Cost stays missing, so cost comparisons leave such runs out rather than counting them free.

## Alternatives Considered

- **Keep ADR-019's completeness comparison**: it never changes the result, and leaves every reader to repeat it.
- **Add a Haiku 5.5 price**: the table would need rules it cannot observe for the figure Claude Code already reports, and an approximate rate would raise false disagreement warnings.
- **Check only run totals**: one unpriced request would still leave the whole run unchecked.
- **A third `source` for a local-model run**: the missing Estimated Cost and its `model_price_unavailable` reason already say why there is no figure, and every reader already handles a missing estimate.

## Relevant PRs

- #251 — records the Run Cost and checks it request by request
