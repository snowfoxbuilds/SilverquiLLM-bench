"""Agent adapters package.

Provides the :class:`AgentAdapter` abstract base class and the
:func:`get_adapter` factory for instantiating concrete adapters by name.
"""

from silverquillm.adapters.base import AgentAdapter, get_adapter, register_adapter

# Import concrete adapters so they auto-register via register_adapter().
import silverquillm.adapters.opencode as _opencode_adapter  # noqa: F401

__all__ = ["AgentAdapter", "get_adapter", "register_adapter"]
