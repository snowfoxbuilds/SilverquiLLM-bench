"""17lands GRE replay data parser and executor.

Parses pre-parsed GRE message streams from 17lands replay exports
into structured ReplayGame objects with game state reconstruction.
The replay executor validates engine behavior against GRE snapshots.
"""

from silverquillm.replay.executor import ReplayExecutor, StateMismatch, StepResult
from silverquillm.replay.parser import parse_replay
from silverquillm.replay.types import (
    GameSnapshot,
    PlayerInfo,
    ReplayAction,
    ReplayGame,
)

__all__ = [
    "parse_replay",
    "GameSnapshot",
    "PlayerInfo",
    "ReplayAction",
    "ReplayGame",
    "ReplayExecutor",
    "StateMismatch",
    "StepResult",
]
