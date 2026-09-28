"""The replay-tool suite drives hob-medium's baseline engine (smoke stages the
same engine). It is engine-development tooling, never staged into a Workspace
or scored: it pins exact divergence counts against recorded games and reads
host-only code."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for path in (_HERE, _HERE.parent / "workspace"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
