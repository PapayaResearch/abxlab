import logging
import time
import functools
from pathlib import Path
from typing import Literal, Optional

import importlib

from browsergym.core import _get_global_playwright
from browsergym.core.action.highlevel import HighLevelActionSet
from browsergym.core.chat import Chat
from browsergym.core.constants import BROWSERGYM_ID_ATTRIBUTE
from browsergym.core.task import AbstractBrowserTask
from browsergym.core.env import BrowserEnv


logger = logging.getLogger(__name__)


class NudgeLabBrowserEnv(BrowserEnv):
    """Override for route handling."""
    def __init__(
        self,
        task_entrypoint: type[AbstractBrowserTask],
        task_kwargs: dict = {},
        viewport: Optional[dict] = None,
        slow_mo: Optional[int] = None,
        timeout: Optional[int] = None,
        locale: Optional[str] = None,
        timezone_id: Optional[str] = None,
        tags_to_mark: Literal["all", "standard_html"] = "standard_html",
        headless: bool = True,
        wait_for_user_message: bool = False,
        terminate_on_infeasible: bool = True,
        resizeable_window: bool = False,
        record_video_dir: Optional[str] = None,
        pw_chromium_kwargs: dict = {},
        pw_context_kwargs: dict = {},
        action_mapping: Optional[callable] = HighLevelActionSet().to_python_code
    ) -> None:
        super().__init__(
            task_entrypoint=task_entrypoint,
            task_kwargs=task_kwargs,
            viewport=viewport,
            slow_mo=slow_mo,
            timeout=timeout,
            locale=locale,
            timezone_id=timezone_id,
            tags_to_mark=tags_to_mark,
            headless=headless,
            wait_for_user_message=wait_for_user_message,
            terminate_on_infeasible=terminate_on_infeasible,
            resizeable_window=resizeable_window,
            record_video_dir=record_video_dir,
            pw_chromium_kwargs=pw_chromium_kwargs,
            pw_context_kwargs=pw_context_kwargs,
            action_mapping=action_mapping
        )

        # Load config file if specified in task_kwargs
        self.env_config = task_kwargs["config"]

        self.reset()

    def reset(self, seed=None, *args, **kwargs):
        if hasattr(self, "context") and self.context:
            self.context.unroute("**/*")

        obs, info = super().reset(seed=seed, *args, **kwargs)

        # Route calls to complete interventions
        if self.env_config and "choices" in self.env_config:
            self.setup_route_handler(self.context)

        return obs, info

    def setup_route_handler(self, context):
        """Setup route handler for modifying HTML based on choice configurations"""

        # Enable response interception for all HTML documents
        def modify_html(route, request, task):

            response = route.fetch()
            if response.ok:
                # Modify the HTML before passing it to the browser and agent
                html = response.body()

                # First we'll do any task-specific preprocessing
                html = task.process_html(html)

                # Find if there's a choice architecture for the current url
                choice = next(
                    filter(
                        lambda choice: choice["url"] in [request.url, "*"], self.env_config.get("choices")
                    ),
                    None
                )

                if choice is not None:
                    for f in choice["functions"]:
                        module_name = f["module"]
                        func_name = f["name"]
                        args = f["args"]

                        module = importlib.import_module(module_name)
                        func = getattr(module, func_name)

                        html, metadata = func(html, **args)

                        metadata["url"] = request.url
                        metadata["timestamp"] = time.time()
                        metadata["function"] = {
                            "name": func_name,
                            "args": args,
                            "module": module_name
                        }

                        task.nudge_metadata.append(metadata)


                route.fulfill(
                    status=response.status,
                    headers=response.headers,
                    body=html,
                )
            else:
                route.continue_()

        # Apply the interception to the entire browser context
        context.route("**/*", functools.partial(modify_html, task=self.task))
