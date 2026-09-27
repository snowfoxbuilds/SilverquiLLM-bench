Status: RETIRED

Last updated: 2026-09-26

# Benchmark Candidates

This page recorded the bench-side lifecycle of Candidate Bundles: promoting a TheOzolith worker-type definition into a public `candidates/` tree, queuing its runs for a batch scheduler, and publishing its results into `published/`.
That pipeline is removed; SilverquiLLM now runs only Karn constructs, as described in [Karn Benchmark Contract](KARN-BENCHMARK-CONTRACT.md).

## What remains

- Historical Run Records, including `ozolith-v1` identities, stay readable without Ozolith; each carries its vendored bundle under `results/<hash>/candidate/`.
- The vendored [Bench Contract](BENCH-CONTRACT.md) remains the reference for interpreting those records.
- Batch files and state in the Candidate Bundle format are shown as unsupported and never run or rewritten; the Karn batch format is in [batches/README.md](../../batches/README.md).
- Nothing was published under `published/`, so no published result depends on the removed publish gate.

To run an old candidate again, rebuild it as a Karn construct.

## Relevant ADRs

| ADR | Decision |
| --- | --- |
| [ADR-012](../adr/ADR-012-independent-host-for-karn-benchmark-candidates.md) | The independent v4 consumer has a separate execution and observation contract |
| [ADR-014](../adr/ADR-014-silverquillm-runs-karn-constructs-without-ozolith.md) | SilverquiLLM runs Karn constructs without Ozolith; Candidate Bundle execution is removed |
