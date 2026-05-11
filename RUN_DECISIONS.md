# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.

## Disagreement: Include Mystical Archives (SOA set, cn 1-65)
- **Reviewer comment (strict)**: Add a test that patches the fetch/cache paths and verifies `fetch_sos_data()` produces exactly 65 `set_code="soa"` cards with collector numbers 1-65.
- **Implementer justification**: The strict comment targets a test file, and the Implementer was instructed not to modify tests.
- **Coordinator decision**: accept reviewer; send the test gap to the Tester.
- **Reasoning**: The TODO's testability requirement is about the public fetch workflow, not only normalization helpers, so the test suite should exercise `fetch_sos_data()` with mocked network/cache paths.
- **Impact**: `tests/test_soa_mystical_archives.py`.
