"""Card execution strategies.

Defines the ``CardStrategy`` abstract base class and concrete strategy
implementations for *blind* and *impl_test* benchmark modes.  A factory
function :func:`get_strategy` maps a mode string to the appropriate
strategy instance.
"""

from __future__ import annotations

import enum
import subprocess
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from silverquillm.adapters.base import AgentAdapter

from silverquillm.prompts import blind_mode_prompt, impl_test_mode_prompt


# ---------------------------------------------------------------------------
# CardRunResult
# ---------------------------------------------------------------------------

class CardRunStatus(enum.Enum):
    """Outcome status for a single card run."""

    completed = "completed"
    timeout = "timeout"
    no_output = "no_output"


@dataclass
class CardRunResult:
    """Result of executing a single card through a strategy.

    Attributes
    ----------
    status:
        Outcome status of the card run.
    files_written:
        Paths written/modified during the run.
    runtime_ms:
        Wall-clock milliseconds elapsed.
    engine_modified:
        Whether the shared engine directory was modified.
    """

    status: CardRunStatus
    files_written: list[Path] = field(default_factory=list)
    runtime_ms: int = 0
    engine_modified: bool = False


# ---------------------------------------------------------------------------
# CardStrategy ABC
# ---------------------------------------------------------------------------

class CardStrategy(ABC):
    """Abstract base class for card execution strategies."""

    @abstractmethod
    def run_card(
        self,
        card_spec: dict[str, Any],
        workspace: Path,
        adapter: Any,
        timeout: int,
    ) -> CardRunResult:
        """Execute a single card and return the result.

        Parameters
        ----------
        card_spec:
            Parsed card specification dictionary.
        workspace:
            Working directory for the card implementation.
        adapter:
            Agent adapter instance to drive the implementation.
        timeout:
            Maximum wall-clock seconds allowed for the run.

        Returns
        -------
        CardRunResult
            Outcome of the card execution.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Concrete strategies
# ---------------------------------------------------------------------------

class BlindStrategy(CardStrategy):
    """Strategy for *blind* mode — single-shot implementation with no tests."""

    def run_card(
        self,
        card_spec: dict[str, Any],
        workspace: Path,
        adapter: Any,
        timeout: int,
    ) -> CardRunResult:
        """Execute a card in blind mode.

        Sends a single prompt to the adapter and checks whether the agent
        produced ``card_impl.py`` in the workspace.

        Returns :attr:`CardRunStatus.completed` when the file exists,
        :attr:`CardRunStatus.no_output` when it does not, or
        :attr:`CardRunStatus.timeout` when the adapter raises a
        :class:`TimeoutError`.
        """
        start = time.monotonic()
        prompt = blind_mode_prompt(card_spec)
        impl_path = workspace / "card_impl.py"

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(adapter.run, prompt, workspace)
        try:
            future.result(timeout=timeout)
        except (TimeoutError, FuturesTimeoutError, subprocess.TimeoutExpired):
            pool.shutdown(wait=False, cancel_futures=True)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            files = [impl_path] if impl_path.exists() else []
            return CardRunResult(
                status=CardRunStatus.timeout,
                files_written=files,
                runtime_ms=elapsed_ms,
            )
        else:
            pool.shutdown(wait=False)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        if impl_path.exists():
            return CardRunResult(
                status=CardRunStatus.completed,
                files_written=[impl_path],
                runtime_ms=elapsed_ms,
            )

        return CardRunResult(
            status=CardRunStatus.no_output,
            files_written=[],
            runtime_ms=elapsed_ms,
        )


class ImplTestStrategy(CardStrategy):
    """Strategy for *impl_test* mode — single prompt, agent self-manages iteration.

    Sends one prompt that instructs the agent to implement the card **and**
    write tests, iterating on its own until satisfied (or timeout).  After
    the adapter returns (or times out), the strategy checks the workspace
    for ``card_impl.py`` and optionally ``tests.py``.
    """

    def run_card(
        self,
        card_spec: dict[str, Any],
        workspace: Path,
        adapter: Any,
        timeout: int,
    ) -> CardRunResult:
        """Execute a card in impl_test mode.

        Sends a single combined implement+test prompt and lets the agent
        self-manage its iteration loop.  Returns
        :attr:`CardRunStatus.completed` when at least ``card_impl.py``
        exists, :attr:`CardRunStatus.no_output` when it does not, or
        :attr:`CardRunStatus.timeout` on timeout.
        """
        start = time.monotonic()
        prompt = impl_test_mode_prompt(card_spec)
        impl_path = workspace / "card_impl.py"
        tests_path = workspace / "tests.py"

        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(adapter.run, prompt, workspace)
        try:
            future.result(timeout=timeout)
        except (TimeoutError, FuturesTimeoutError, subprocess.TimeoutExpired):
            pool.shutdown(wait=False, cancel_futures=True)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            files: list[Path] = []
            if impl_path.exists():
                files.append(impl_path)
            if tests_path.exists():
                files.append(tests_path)
            return CardRunResult(
                status=CardRunStatus.timeout,
                files_written=files,
                runtime_ms=elapsed_ms,
            )
        else:
            pool.shutdown(wait=False)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        if impl_path.exists():
            files = [impl_path]
            if tests_path.exists():
                files.append(tests_path)
            return CardRunResult(
                status=CardRunStatus.completed,
                files_written=files,
                runtime_ms=elapsed_ms,
            )

        return CardRunResult(
            status=CardRunStatus.no_output,
            files_written=[],
            runtime_ms=elapsed_ms,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_STRATEGY_MAP: dict[str, type[CardStrategy]] = {
    "blind": BlindStrategy,
    "impl_test": ImplTestStrategy,
}

_VALID_MODES = frozenset(_STRATEGY_MAP.keys())


def get_strategy(mode: str) -> CardStrategy:
    """Return the appropriate :class:`CardStrategy` for *mode*.

    Parameters
    ----------
    mode:
        One of ``"blind"`` or ``"impl_test"``.

    Returns
    -------
    CardStrategy
        An instance of the matching strategy class.

    Raises
    ------
    ValueError
        If *mode* is not a recognised strategy name.
    """
    cls = _STRATEGY_MAP.get(mode)
    if cls is None:
        raise ValueError(
            f"Unknown mode {mode!r}; valid modes: {sorted(_VALID_MODES)}"
        )
    return cls()
