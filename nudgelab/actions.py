from dataclasses import dataclass
from browsergym.experiments.benchmark.base import HighLevelActionSetArgs, HighLevelActionSet
from browsergym.core.action.functions import (
    click,
    fill,
    go_back,
    go_forward,
    goto,
    scroll,
    select_option,
    keyboard_press,
    tab_focus
)


@dataclass
class NudgeLabHighLevelActionSetArgs(HighLevelActionSetArgs):
    """
    Custom HighLevelActionSetArgs for NudgeLab.
    """
    subsets = ["custom"]  # Override the subsets to include 'custom'

    def __post_init__(self):
        if isinstance(self.subsets, list):
            """Needs to be hashable for AgentLab when uniquely identifying agents."""
            self.subsets = tuple(self.subsets)

    def make_action_set(self):
        return HighLevelActionSet(
            subsets=self.subsets,
            custom_actions=[
                click,
                fill,
                go_back,
                go_forward,
                goto,
                scroll,
                select_option,
                keyboard_press,
                tab_focus
            ],
            multiaction=self.multiaction,
            strict=self.strict,
            retry_with_force=self.retry_with_force,
            demo_mode=self.demo_mode
        )
