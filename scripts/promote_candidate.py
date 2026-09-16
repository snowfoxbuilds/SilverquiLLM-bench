#!/usr/bin/env python3
"""Promote a standalone Karn definition; source and credential checks precede atomic publication."""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from silverquillm.candidate import CandidateRefusedError
from silverquillm.created_directories import CreatedDirectoryError
from silverquillm.promotion import PromotionCleanupError, promote

DEFAULT_CANDIDATES_DIR = REPO_ROOT / "candidates"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "definition", type=Path, help="standalone definition.json or a directory containing one"
    )
    parser.add_argument("--slug")
    parser.add_argument("--candidates-dir", type=Path, default=DEFAULT_CANDIDATES_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = promote(
            args.definition,
            candidates_dir=args.candidates_dir,
            slug=args.slug,
            dry_run=args.dry_run,
        )
    except PromotionCleanupError as error:
        print("CLEANUP FAILED: " + str(error), file=sys.stderr)
        return 2
    except (CandidateRefusedError, OSError, ValueError, CreatedDirectoryError) as error:
        print("REFUSED: " + str(error), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "candidate": str(result.candidate_dir),
                "written": result.written,
                "identity": result.bundle.identity.to_dict(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
