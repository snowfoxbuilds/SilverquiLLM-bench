# Files Modified (this run)

Appended by each Implementer invocation after it writes its diff. One section per TODO item.

## Item 1: Delete remaining old harness code

### Implementation
- `silverquillm/card_classifier.py` — Deleted (dead code: complexity tier classifier)
- `silverquillm/prototype.py` — Deleted (dead code: prototype card selection)
- `silverquillm/post_eval.py` — Deleted (dead code: post-evaluation aggregation)
- `silverquillm/regression.py` — Deleted (dead code: per-card regression runner)
- `silverquillm/scorer.py` — Deleted (dead code: old 4-category scoring)
- `silverquillm/template_gen.py` — Deleted (dead code: card template generation)
- `silverquillm/card_spec.py` — Added `card_name_to_class_name` and `_determine_base_class` (moved from deleted template_gen.py)
- `tests/test_card_classifier.py` — Deleted (corresponding test for deleted module)
- `tests/test_prototype.py` — Deleted (corresponding test for deleted module)
- `tests/test_post_eval.py` — Deleted (corresponding test for deleted module)
- `tests/test_regression.py` — Deleted (corresponding test for deleted module)
- `tests/test_regression_runner.py` — Deleted (orphaned test importing deleted regression module)
- `tests/test_scorer.py` — Deleted (corresponding test for deleted module)
- `tests/test_template_gen.py` — Deleted (corresponding test for deleted module)
- `tests/test_cat4_scoring.py` — Deleted (orphaned test importing deleted scorer module)
- `tests/test_tier_naming.py` — Removed TestClassifierOutput and TestPrototypeSelector classes (referenced deleted modules)
- `tests/test_soa_mystical_archives.py` — Removed TestClassifySetMultiSet class (referenced deleted card_classifier)
- `tests/test_integration_helpers.py` — Updated import from template_gen to card_spec
- `tests/benchmark/test_helpers.py` — Updated import from template_gen to card_spec
- `scripts/generate_audited_stubs.py` — Updated import from template_gen to card_spec
- `tests/test_results.py` — Deleted (imports deleted scorer module and non-existent results module)
- `tests/test_eval_result_v2.py` — Deleted (imports deleted scorer and post_eval modules)
- `tests/test_postmortem_schema_v2.py` — Deleted (imports deleted post_eval module)
- `tests/benchmark/test_e2e.py` — Deleted (imports deleted scorer module)
- `tests/benchmark/test_helpers.py` — Deleted (orphaned helper importing non-existent config module)
- `tests/test_package_rename.py` — Removed deleted modules from _EXPECTED_SUBMODULES list


## Item 2: Restructure FDN cards to per-collector-number layout (completion)

### Tests
- `tests/test_fdn_restructure.py` — Verifies per-card directory structure, importability, monolithic file deletion, registry

### Implementation
- `cards/fdn/*/card_impl.py` (264 files) — Made self-contained: extracted class definitions and helpers from monolithic files
- `cards/foundations/` (24 files deleted) — Removed monolithic .py files, replaced with package-based compatibility shims
- `cards/foundations/{module_name}/__init__.py` (22 shim packages) — Re-export card classes via importlib from new per-card locations
- `cards/fdn/_land_bases.py` — Shared TapLand/GainLand base classes for all non-basic lands
- `cards/fdn/547/card_impl.py` — Added SkryakerGiant legacy alias
- `cards/fdn/spg_79/card_impl.py` — Fixed missing _COLOR_TO_MANA dict for BloomTender
- `cards/fdn/259-271/card_impl.py` (10 land files) — Updated to import from shared _land_bases module


## Item 3: Restructure SOS cards to unified cards/ layout

### Implementation
- `cards/sos/__init__.py` — Package init for SOS cards directory
- `cards/sos/{1..271}/card_spec.json` — Copied SOS base card specs (271 files)
- `cards/sos/{1..271}/card_impl.py` — Generated SOS base card implementation templates (271 files)
- `cards/sos/soa_{1..65}/card_spec.json` — Copied SOA Mystical Archives card specs (65 files)
- `cards/sos/soa_{1..65}/card_impl.py` — Generated SOA card implementation templates (65 files)
- `cards/sos/spg_{149..158}/card_spec.json` — Copied SPG Special Guests card specs (10 files)
- `cards/sos/spg_{149..158}/card_impl.py` — Generated SPG card implementation templates (10 files)
- `benchmarks/sos/cards/{1..271,soa_*,spg_*}/` — Deleted 346 old card subdirectories (cleanup after migration)

## Item 4: Rewrite card_loader.py for unified card layout

### Tests
- `tests/test_card_loader.py` — Tests load_card_specs, load_prototype_cards, filter_by_collectors, filter_by_prototype
- `tests/test_card_loader_unified.py` — Tests unified layout functions (load_card_spec, load_all_card_specs, load_card_impl, is_template)

### Implementation
- `silverquillm/card_loader.py` — Added unified layout functions with path-derived identifiers, natural dir-name sorting, and fixed is_template to only skip docstrings/ellipsis

## Item 5: Implement workspace.py — workspace staging

### Tests
- `tests/test_workspace.py` — 30 tests verifying workspace structure, engine copy, FDN/SOS cards, reference docs, idempotency

### Implementation
- `silverquillm/workspace.py` — workspace staging module with `stage_workspace()` that builds Docker mount directory tree; revised to add stale cleanup, use engine_dir for base_classes.py, and copy shared tier-level helper files

## Item 6: Create Docker images for opencode-tested and opencode-blind

### Implementation
- `docker/opencode-tested/Dockerfile` — Docker image definition for test-informed opencode agent
- `docker/opencode-tested/entrypoint.sh` — Entrypoint script with test-writing prompt, engine_work instruction, and set+e wait fix
- `docker/opencode-blind/Dockerfile` — Docker image definition for blind opencode agent
- `docker/opencode-blind/entrypoint.sh` — Entrypoint script with spec-only prompt, engine_work instruction, and set+e wait fix
