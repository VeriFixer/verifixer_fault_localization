from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class NodeSelectionPolicy:
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

NODE_SELECTION_POLICY_REGULAR = NodeSelectionPolicy("regular")
NODE_SELECTION_POLICY_PURE_STATE = NodeSelectionPolicy("pure_state")

SUPPORTED_NODE_SELECTION_POLICIES = (
    NODE_SELECTION_POLICY_REGULAR,
    NODE_SELECTION_POLICY_PURE_STATE,
)


@dataclass(frozen=True)
class CounterExampleRankingControls:
    node_selection_policy: NodeSelectionPolicy = NODE_SELECTION_POLICY_REGULAR
    use_frequency: bool = True
    use_depth: bool = True
    use_control_statement: bool = True


DEFAULT_COUNTEREXAMPLE_RANKING_CONTROLS = CounterExampleRankingControls()

CNTM_ABLATION_PURE_STATE = CounterExampleRankingControls(
    node_selection_policy=NODE_SELECTION_POLICY_PURE_STATE,
)

CNTM_ABLATION_NO_FREQUENCY = CounterExampleRankingControls(
    use_frequency=False,
)

CNTM_ABLATION_NO_DEPTH = CounterExampleRankingControls(
    use_depth=False,
)

CNTM_ABLATION_NO_CONTROL = CounterExampleRankingControls(
    use_control_statement=False,
)
