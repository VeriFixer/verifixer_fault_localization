from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class RankingStrategy:
    name: str


@dataclass(frozen=True)
class CounterExampleNode:
    line: int
    depth: int
    type: str
    source: str
    content: str
    trace_id: int
    parents: list[tuple[str, int]] = field(default_factory=list)


RANK_BY_FREQUENCY = RankingStrategy("frequency")
RANK_BY_ORDER = RankingStrategy("order")
RANK_BY_DEPTH_DEEPER_FIRST = RankingStrategy("depth_deeper_first")

SUPPORTED_RANKING_STRATEGIES = (
    RANK_BY_FREQUENCY,
    RANK_BY_ORDER,
    RANK_BY_DEPTH_DEEPER_FIRST,
)
