import logging
import time
from pathlib import Path
from typing import Literal, Optional

import playwright.sync_api
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
        super().reset(seed=seed, *args, **kwargs)
        self.np_random = None  # make sure all randomness is handled by the task

        if self.task:
            self.task.teardown()
            self.context.close()
            self.chat.close()
            self.browser.close()

        # create a new task
        self.task = self.task_entrypoint(seed=seed, **self.task_kwargs)

        def override_property(task, env, property):
            """Extract property value from env if not None, otherwise from task."""
            env_value = getattr(env, property)
            task_value = getattr(task, property)
            if env_value is None:
                return task_value
            else:
                if task_value is not None:
                    logger.warning(
                        f"Overriding the task's {property} parameter ({repr(task_value)} => {repr(env_value)}). This might change the task's behaviour and difficulty."
                    )
                return env_value

        # fetch task's desired parameters for browser setup
        viewport = override_property(self.task, self, "viewport")
        slow_mo = override_property(self.task, self, "slow_mo")
        timeout = override_property(self.task, self, "timeout")
        locale = override_property(self.task, self, "locale")
        timezone_id = override_property(self.task, self, "timezone_id")

        # use the global Playwright instance
        pw: playwright.sync_api.Playwright = _get_global_playwright()
        # important: change playwright's test id attribute from "data-testid" to "bid"
        pw.selectors.set_test_id_attribute(BROWSERGYM_ID_ATTRIBUTE)

        # create a new browser
        self.browser = pw.chromium.launch(
            headless=self.headless,
            slow_mo=slow_mo,
            args=(
                [f"--window-size={viewport['width']},{viewport['height']}"]
                if self.resizeable_window
                else None
            ),
            # will raise an Exception if above args are overriden
            **self.pw_chromium_kwargs,
        )

        # create a new browser context for pages
        self.context = self.browser.new_context(
            no_viewport=True if self.resizeable_window else None,
            viewport=viewport if not self.resizeable_window else None,
            record_video_dir=(
                Path(self.record_video_dir) / "task_video" if self.record_video_dir else None
            ),
            record_video_size=viewport,
            locale=locale,
            timezone_id=timezone_id,
            # will raise an Exception if above args are overriden
            **self.pw_context_kwargs,
        )

        # set default timeout
        self.context.set_default_timeout(timeout)

        # Route calls to complete interventions
        if self.env_config and "choices" in self.env_config:
            self.setup_route_handler(self.context)

        # hack: keep track of the active page with a javascript callback
        # there is no concept of active page in playwright
        # https://github.com/microsoft/playwright/issues/2603
        self.context.expose_binding(
            "browsergym_page_activated", lambda source: self._activate_page_from_js(source["page"])
        )
        self.context.add_init_script(
            r"""
window.browsergym_page_activated();
window.addEventListener("focus", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("focusin", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("load", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("pageshow", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("mousemove", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("mouseup", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("mousedown", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("wheel", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("keyup", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("keydown", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("input", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("touchstart", () => {window.browsergym_page_activated();}, {capture: true});
window.addEventListener("touchend", () => {window.browsergym_page_activated();}, {capture: true});
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
        window.browsergym_page_activated();
    }
}, {capture: true});
"""
        )

        # create the chat
        self.chat = Chat(
            headless=self.headless,
            chat_size=(500, max(viewport["height"], 800)),
            record_video_dir=self.record_video_dir,
        )

        # create a new page
        self.page = self.context.new_page()
        recording_start_time = time.time()

        # setup the task
        task_goal, task_info = self.task.setup(page=self.page)

        # process the task goal

        # no goal specified
        if task_goal is None:
            self.goal_object = []
        # convert text-only goal (legacy) to new format
        elif isinstance(task_goal, str):
            self.goal_object = [{"type": "text", "text": task_goal}]
        # new format goal with multiple texts and images (OpenAI style)
        elif isinstance(task_goal, list):
            self.goal_object = task_goal
        else:
            raise ValueError(f"task_goal should be of type str or list, got {task_goal.__class__}")

        # initialize the chat
        self.chat.add_message(
            role="assistant",
            msg="Hi! I am your UI assistant, I can perform web tasks for you. What can I help you with?",
        )

        # send task goal (if any) to the chat
        for message in self.goal_object:
            match message["type"]:
                case "text":
                    self.chat.add_message(role="user", msg=message["text"])
                case "image_url":
                    image_src = message["image_url"]
                    if isinstance(image_src, dict):
                        image_src = image_src["url"]
                    self.chat.add_message(role="user_image", msg=image_src)
                case _:
                    raise ValueError(
                        f"Unknown message type {repr(message['type'])} in the task goal."
                    )

        self._wait_dom_loaded()

        # after the task's setup, the active page might have changed
        # perform a safety check
        self._active_page_check()

        # init start time
        self.start_time = time.time()

        # no action yet
        self.last_action = ""
        self.last_action_error = ""
        self.infeasible_message_received = False

        # if asked, wait for user message
        self._wait_for_user_message()

        # extract obs and info from environment
        obs = self._get_obs()

        info = {}
        info["task_info"] = task_info

        # TODO this is a bit hacky, find a better solution to record videos
        if self.record_video_dir:
            info["recording_start_time"] = recording_start_time
            info["recording_file"] = str(self.page.video.path())
            info["chat"] = {
                "recording_start_time": self.chat.recording_start_time,
                "recording_file": str(self.chat.page.video.path()),
            }

        return obs, info

    def setup_route_handler(self, context):
        """Setup route handler for modifying HTML based on choice configurations"""

        # Enable response interception for all HTML documents
        def modify_html(route, request):

            response = route.fetch()
            if response.ok:
                # Modify the HTML before passing it to the browser and agent
                html = response.body()

                # First we'll do any task-specific preprocessing
                html = self.task.process_html(html)

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

                        self.task.nudge_metadata.append(metadata)


                route.fulfill(
                    status=response.status,
                    headers=response.headers,
                    body=html,
                )
            else:
                route.continue_()

        # Apply the interception to the entire browser context
        context.route("**/*", modify_html)
