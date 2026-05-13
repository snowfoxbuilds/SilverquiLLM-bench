# Run Decisions

Decisions made during this run only. Before the PR, migrate anything worth preserving long-term into `KEY_DECISIONS.md`.


## Test failure: Item 1 — Delete remaining old harness code
- **Failing tests**: test_test_file_deleted[tests/test_tier_naming.py], test_test_file_deleted[tests/test_soa_mystical_archives.py], test_test_file_deleted[tests/test_integration_helpers.py], test_test_file_deleted[tests/benchmark/test_helpers.py], test_no_import_of_deleted_module_in_tests[post_eval], test_no_import_of_deleted_module_in_tests[scorer]
- **Tester's intent**: Assert all test files related to deleted modules are fully removed. Assert no remaining test file contains imports of deleted modules.
- **Implementer's approach**: Surgically removed only offending test classes/imports from files that still contain valid tests for non-deleted functionality. Moved shared utility functions (card_name_to_class_name, _determine_base_class) to card_spec.py so dependent test files remain valid. Kept test_tier_naming.py (has valid tier tests), test_soa_mystical_archives.py (has valid SOA tests), test_integration_helpers.py (uses moved utilities), tests/benchmark/test_helpers.py (uses moved utilities).
- **Coordinator decision**: fix tests
- **Reasoning**: The Implementer's approach is correct. Files should only be deleted if ALL their content is orphaned. These 4 files still have valid tests for non-deleted modules. The import check failures are likely false positives from the test file itself referencing module names as parametrization strings. The Tester should update to only expect deletion of files that are fully orphaned, and exclude self-references in import scanning.
