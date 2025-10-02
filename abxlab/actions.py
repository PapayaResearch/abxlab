# Copyright (c) 2025
# Manuel Cherep <mcherep@mit.edu>
# Nikhil Singh <nikhil.u.singh@dartmouth.edu>

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Code adapted from BrowserGym (https://github.com/ServiceNow/BrowserGym/tree/main).
You can replace ABxLabHighLevelActionSetArgs and ABxLabHighLevelActionSet if you
want to customize the action set.
"""

import inspect
import typing
from dataclasses import dataclass
from browsergym.experiments.benchmark.base import HighLevelActionSetArgs
from browsergym.core.action.highlevel import HighLevelAction, HighLevelActionSet, ACTION_SUBSETS
from browsergym.core.action.parsers import action_docstring_parser
from browsergym.core.action.highlevel import utils
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


class ABxLabHighLevelActionSet(HighLevelActionSet):
    """
    Custom HighLevelActionSet for ABxLab.
    """

    # static class variables
    ActionSubset = typing.Literal[
        "chat",
        "infeas",
        "bid",
        "coord",
        "nav",
        "tab",
        "miniwob_all",
        "miniwob_shi17",
        "miniwob_liu18",
        "miniwob_humphreys22",
        "webarena",
        "visualwebarena",
        "workarena",
        "workarena++",
        "weblinx",
        "assistantbench",
        "custom",
    ]
    DemoMode = typing.Literal["off", "default", "all_blue", "only_visible_elements"]

    def __init__(
        self,
        subsets: typing.Optional[ActionSubset | list[ActionSubset]] = [
            "chat",
            "infeas",
            "bid",
            "nav",
            "tab",
        ],
        custom_actions: typing.Optional[list[callable]] = None,
        multiaction: bool = True,
        demo_mode: typing.Optional[DemoMode] = None,
        strict: bool = False,
        retry_with_force: bool = False,
    ):
        # Get the grandparent class
        super(HighLevelActionSet, self).__init__(strict)
        self.multiaction = multiaction
        self.demo_mode = demo_mode
        self.retry_with_force = retry_with_force

        if not subsets:
            raise ValueError(f"'action_subsets' is empty.")

        if isinstance(subsets, str):
            subsets = [subsets]

        allowed_actions = []  # the noop action is NOT allowed

        # add actions from specified action sets
        if subsets:
            for subset in subsets:
                if subset in ACTION_SUBSETS:
                    allowed_actions.extend(ACTION_SUBSETS[subset])
                elif subset == "custom":
                    if not custom_actions:
                        raise ValueError(
                            "'custom' is in 'action_subsets' but 'custom_actions' is empty."
                        )
                    allowed_actions.extend(custom_actions)
                else:
                    raise ValueError(f"Unknown high-level action subspace: {subset}")

        # like set() but preserves order
        # https://stackoverflow.com/questions/1653970/does-python-have-an-ordered-set
        allowed_actions = list(dict.fromkeys(allowed_actions).keys())

        # parse the actions and build the action space
        self.action_set: dict[str, HighLevelAction] = {}
        self.python_includes = ""

        # include playwright imports
        self.python_includes += f"""\
import playwright.sync_api
from typing import Literal


"""
        # set demo_mode and retry_with_force flags
        self.python_includes += f"""\
demo_mode={repr(demo_mode)}
retry_with_force={repr(retry_with_force)}

if demo_mode is None:
    demo_mode = "default" if DEMO_MODE else "off"

"""

        # include utility functions
        for _, func in inspect.getmembers(utils, inspect.isfunction):
            self.python_includes += f"""\
{inspect.getsource(func)}


"""

        # parse and include action functions
        for func in allowed_actions:

            # include action function definition in the code
            self.python_includes += f"""\
{inspect.getsource(func)}


"""

            # extract action signature
            signature = f"{func.__name__}{inspect.signature(func)}"

            # parse docstring
            description, examples = action_docstring_parser.parse_string(func.__doc__)

            # reconstruct action description
            description = " ".join(description)

            # reconstruct action examples
            examples = [
                function_name + "(" + ", ".join([repr(arg) for arg in function_args]) + ")"
                for function_name, function_args in examples
            ]

            if func.__name__ in self.action_set:
                raise ValueError(f"Duplicated action '{func.__name__}'")

            self.action_set[func.__name__] = HighLevelAction(
                # entrypoint=func,
                signature=signature,
                description=description,
                examples=examples,
            )


@dataclass
class ABxLabHighLevelActionSetArgs(HighLevelActionSetArgs):
    """
    Custom HighLevelActionSetArgs for ABxLab.
    """
    subsets = ["custom"]  # Override the subsets to include 'custom'

    def __post_init__(self):
        if isinstance(self.subsets, list):
            """Needs to be hashable for AgentLab when uniquely identifying agents."""
            self.subsets = tuple(self.subsets)

    def make_action_set(self):
        return ABxLabHighLevelActionSet(
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
