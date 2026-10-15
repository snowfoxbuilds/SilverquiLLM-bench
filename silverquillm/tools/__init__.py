"""Benchmark-construction and maintenance tooling behind the ``silverquillm`` commands.

Each module keeps a ``main(argv)`` entry point; ``silverquillm.tools.cli`` exposes
them as command groups. The modules read and write the bench checkout they are
imported from, so ``REPO_ROOT`` is that checkout.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
