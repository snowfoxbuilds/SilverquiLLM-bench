Status: ACCEPTED
Date: 2026-09-26

# ADR-0012: Execute Karn Candidates through an Independent Benchmark Host

## Context

The existing Candidate Bundle integration imports Ozolith's builder and production workflow implementation.
Karn now produces versioned Construct Definitions independently of Ozolith's runtime.
The bench needs to evaluate those artifacts while owning task delivery, execution budgets, and local grading, so run data can inform iterative improvement.

## Decision

Karn builds the candidate before execution.
An independent benchmark host consumes the resulting immutable image and v4 Construct Definition without requiring an Ozolith Node Daemon.
The benchmark host owns scheduling and task delivery and implements the runtime facilities the selected candidate declares.
The first implementation covers a limited set of runtime facilities without requiring an exhaustive rejection layer for all other facilities.

Karn allows controller-free Automatons; a controller is required for automatic scheduling, not direct execution (amended 2026-09-26).
External launch does not waive selected authentication or other lifecycle hooks.
The bench never rebuilds a recipe implicitly when a queued run starts, and build time does not consume the Benchmark Run's execution budget.

## Consequences

- **Positive**: Benchmark execution has no dependency on production issue polling, claims, or publication.
- **Positive**: The recorded candidate identifies the built artifact actually executed.
- **Negative**: The bench must implement and validate its own supported runtime facilities, including the selected login lifecycle.
- **Neutral**: Karn's composition validator permits controller-free builds; the benchmark directly launches the resulting definition.
- **Neutral**: A valid Karn definition can require facilities a particular benchmark host does not support.

## Alternatives Considered

- **Run benchmarks through an Ozolith Node Daemon**: Rejected because it adds runtime deployment and lifecycle dependencies to the benchmark host.
- **Attach an unused polling plugin to pass the builder's check**: Rejected because passing composition validation does not define the external execution contract.
- **Build implicitly at run start**: Rejected because execution should consume an explicit built artifact and have a budget independent of its build.

## Amendments

- **2026-09-26**: Recorded the landed producer support for controller-free Automatons, verified by a real bare Codex build with only its login plugin.
