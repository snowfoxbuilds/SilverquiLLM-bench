"""Abstract base class for agent adapters and adapter factory.

Every concrete adapter must subclass :class:`AgentAdapter` and implement
the three abstract methods: :meth:`run`, :meth:`setup`, and :meth:`teardown`.

Use :func:`get_adapter` to obtain an adapter instance from a
:class:`~silverquillm.config.BenchmarkConfig`.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Type

from silverquillm.config import BenchmarkConfig


class AgentAdapter(ABC):
    """Base class for agent adapters.

    Parameters
    ----------
    config:
        The benchmark configuration.  Concrete adapters may read
        adapter-specific keys from ``config.agent``.
    """

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def setup(self) -> None:
        """Prepare the adapter (e.g. start a subprocess, authenticate)."""

    @abstractmethod
    def run(self, prompt: str, workspace: Path) -> str:
        """Send *prompt* to the agent working in *workspace* and return its reply.

        Parameters
        ----------
        prompt:
            The full prompt text to send.
        workspace:
            Directory the agent should treat as its working directory.

        Returns
        -------
        str
            The agent's textual response.
        """

    @abstractmethod
    def teardown(self) -> None:
        """Clean up resources held by the adapter."""

    # ------------------------------------------------------------------
    # Kill (hard timeout support)
    # ------------------------------------------------------------------

    def kill(self) -> None:
        """Forcibly terminate any running subprocess or background work.

        Called by the strategy layer when a hard timeout fires to ensure
        child processes are actually terminated rather than left orphaned.
        Subclasses that spawn subprocesses **must** override this.

        The default implementation is a no-op.
        """

    # ------------------------------------------------------------------
    # Timeout / retry helper
    # ------------------------------------------------------------------

    def run_with_retries(
        self,
        prompt: str,
        workspace: Path,
        *,
        retries: int = 2,
        timeout: int | None = None,
    ) -> str:
        """Call :meth:`run` with retry and timeout logic.

        Parameters
        ----------
        prompt:
            Prompt to send.
        workspace:
            Working directory for the agent.
        retries:
            Number of retry attempts after the initial call (default ``2``).
        timeout:
            Overall timeout budget in seconds across **all** attempts.
            Defaults to ``config.agent.timeout_per_card``.

        Returns
        -------
        str
            The agent's response.

        Raises
        ------
        TimeoutError
            If every attempt exceeds *timeout*.
        RuntimeError
            If every attempt raises an unexpected exception.
        """
        if timeout is None:
            timeout = self.config.agent.timeout_per_card

        deadline = time.monotonic() + timeout
        last_exc: BaseException | None = None
        for attempt in range(1 + retries):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if last_exc is None:
                    last_exc = TimeoutError(
                        f"Agent adapter timed out (budget exhausted)"
                    )
                break
            attempt_timeout = max(1, int(round(remaining)))
            try:
                return self._run_with_timeout(prompt, workspace, attempt_timeout)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                # Exponential back-off: 1s, 2s, 4s, …
                if attempt < retries:
                    time.sleep(min(2**attempt, 30))

        if isinstance(last_exc, TimeoutError):
            self.kill()
            raise last_exc

        raise RuntimeError(
            f"Agent adapter failed after {1 + retries} attempts"
        ) from last_exc

    def _run_with_timeout(
        self, prompt: str, workspace: Path, timeout: int
    ) -> str:
        """Execute :meth:`run` enforcing a wall-clock *timeout*.

        Uses ``signal.SIGALRM`` on Unix when called from the main thread.
        Falls back to the threading implementation on Windows or when called
        from a non-main thread (``signal.signal`` raises ``ValueError`` in
        non-main threads).
        """
        import sys
        import threading

        if sys.platform == "win32" or not (
            threading.current_thread() is threading.main_thread()
        ):
            return self._run_with_timeout_threading(prompt, workspace, timeout)

        import signal

        def _handler(signum: int, frame: object) -> None:
            raise TimeoutError(
                f"Agent adapter timed out after {timeout}s"
            )

        old = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(timeout)
        try:
            result = self.run(prompt, workspace)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        return result

    def _run_with_timeout_threading(
        self, prompt: str, workspace: Path, timeout: int
    ) -> str:
        """Threading-based timeout fallback used on Windows."""
        import threading

        result: list[str] = []
        exc_holder: list[BaseException] = []

        def _target() -> None:
            try:
                result.append(self.run(prompt, workspace))
            except BaseException as exc:  # noqa: BLE001
                exc_holder.append(exc)

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            raise TimeoutError(f"Agent adapter timed out after {timeout}s")
        if exc_holder:
            raise exc_holder[0]
        return result[0]


# ------------------------------------------------------------------
# Adapter registry & factory
# ------------------------------------------------------------------

_ADAPTER_REGISTRY: dict[str, Type[AgentAdapter]] = {}


def register_adapter(name: str, cls: Type[AgentAdapter]) -> None:
    """Register *cls* as the adapter for *name*.

    Parameters
    ----------
    name:
        Short identifier (e.g. ``"opencode"``).
    cls:
        A concrete :class:`AgentAdapter` subclass.
    """
    _ADAPTER_REGISTRY[name] = cls


def get_adapter(config: BenchmarkConfig) -> AgentAdapter:
    """Instantiate the adapter specified by ``config.agent.adapter``.

    Parameters
    ----------
    config:
        Benchmark configuration whose ``agent.adapter`` field names the
        adapter to use.

    Returns
    -------
    AgentAdapter
        A ready-to-use (but **not** yet set-up) adapter instance.

    Raises
    ------
    ValueError
        If no adapter is registered under the requested name.
    """
    name = config.agent.adapter
    cls = _ADAPTER_REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(_ADAPTER_REGISTRY)) or "(none)"
        raise ValueError(
            f"Unknown adapter {name!r}. Available adapters: {available}"
        )
    return cls(config)
