import importlib.resources
import json
import logging
import tempfile
import urllib.parse
from typing import Optional, Tuple

import numpy as np
import playwright.sync_api

from browsergym.core.task import AbstractBrowserTask
from browsergym.nudgingarena.instance import WebArenaInstance

logger = logging.getLogger(__name__)


class GenericWebArenaTask(AbstractBrowserTask):
    """Task for nudging experiments"""

    def __init__(
        self,
        seed: int,
        config_file: str,
        with_na_hint: bool = False,
        with_homepage_hint: bool = False,
    ) -> None:
        super().__init__(seed)

        # task properties
        self.viewport = {"width": 1280, "height": 720}
        self.slow_mo = 1000  # ms
        self.timeout = 10000  # ms

        self.webarena_instance = WebArenaInstance()
        self.with_na_hint = with_na_hint
        self.with_homepage_hint = with_homepage_hint

        # Load config directly from file
        import nudgingarena
        config_path = importlib.resources.files(nudgingarena).joinpath(config_file)
        with open(config_path) as f:
            self.config = json.load(f)
            self.config_file = str(config_path)

    def setup(self, page: playwright.sync_api.Page) -> tuple[str, dict]:
        # import webarena on instanciation
        from nudgingarena.evaluation_harness.evaluators import evaluator_router
        self.evaluator = evaluator_router(self.config_file)

        # authenticate if needed
        if self.config.get("require_login"):
            for site in self.config["sites"]:
                self.webarena_instance.ui_login(site=site, page=page)

        # set geolocation if specified
        if self.config.get("geolocation"):
            page.context.set_geolocation(self.config["geolocation"])

        # navigate to start URL
        if self.config["start_url"]:
            page.goto(self.config["start_url"])

        return self.config["intent"], {}

    def cheat(self, page: playwright.sync_api.Page, chat_messages: list[str]) -> None:
        raise NotImplementedError

    @classmethod
    def get_task_id(cls):
        """
        Generic class for several task ids, this way of obtaining the task id is not compatible for now.
        """
        raise NotImplementedError

    def teardown(self) -> None:
        pass

    def validate(
        self, page: playwright.sync_api.Page, chat_messages: list[str]
    ) -> Tuple[float, bool, str, dict]:
        # Use last assistant message as answer
        if chat_messages and chat_messages[-1]["role"] == "assistant":
            answer = chat_messages[-1]["message"]
        else:
            answer = ""

        # Create minimal trajectory for evaluator
        trajectory = [{}, {"action_type": "stop", "answer": answer}]

        # Evaluate
        try:
            score = self.evaluator(
                trajectory=trajectory,
                config_file=self.config_file,
                page=page,
                client=None,
            )
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            score = 0.0

        done = score > 0
        return score, done, "", {}
