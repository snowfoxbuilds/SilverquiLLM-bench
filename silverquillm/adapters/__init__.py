"""Agent adapters package.

Provides the :class:`AgentAdapter` abstract base class and the
:func:`get_adapter` factory for instantiating concrete adapters by name.
"""

from silverquillm.adapters.base import AgentAdapter, get_adapter, register_adapter

__all__ = ["AgentAdapter", "get_adapter", "register_adapter"]
