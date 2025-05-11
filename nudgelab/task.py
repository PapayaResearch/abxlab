import os
import logging
import urllib.parse
import yaml
import playwright.sync_api
from bs4 import BeautifulSoup
from nudgelab.evaluators import evaluator_router
from browsergym.core.task import AbstractBrowserTask
from browsergym.webarena.instance import WebArenaInstance
from nudgelab.choices.shop.home import rating as home_rating
from nudgelab.choices.shop.category import rating as category_rating
from nudgelab.choices.shop.product import rating as product_rating


logger = logging.getLogger(__name__)


class NudgeLabTask(AbstractBrowserTask):
    """
    Base class for all NudgeLab tasks.
    """
    def __init__(
        self,
        seed: int,
        config: dict,
        with_na_hint: bool = False,
        with_homepage_hint: bool = False,
        width: int = 1280,
        height: int = 720,
        slow_mo: int = 1000, # ms
        timeout: int = 10000, # ms
        study_dir: str = "",
        **kwargs
    ) -> None:
        super().__init__(seed)

        # Task properties, will be used to set up the browsergym environment
        self.viewport = {"width": width, "height": height}
        self.slow_mo = slow_mo
        self.timeout = timeout

        self.webarena_instance = WebArenaInstance()
        self.with_na_hint = with_na_hint
        self.with_homepage_hint = with_homepage_hint

        # Load config directly from a dict
        self.config = config

        self.study_dir = study_dir

    def setup(self, page: playwright.sync_api.Page) -> tuple[str, dict]:
        # build the evaluator
        self.evaluator = evaluator_router(self.config)

        # authenticate if needed
        if self.config.get("require_login"):
            for site in self.config["sites"]:
                self.webarena_instance.ui_login(site=site, page=page)

        # set geolocation if specified
        if self.config.get("geolocation"):
            page.context.set_geolocation(self.config["geolocation"])

        # navigate to the starting url(s) (might need several pages)
        # https://github.com/web-arena-x/webarena/blob/c6475f0e9affe5252a2966e26b8cb4c834a4ae40/browser_env/envs.py#L150
        if self.config["start_urls"]:
            start_urls = self.config["start_urls"]
            for i, url in enumerate(start_urls):
                page.goto(url)
                if i < len(start_urls) - 1:
                    page = page.context.new_page()

        # recover goal
        goal = self.config["intent"]

        # This note is present in all webarena's agent prompts
        # https://github.com/web-arena-x/webarena/blob/c6475f0e9affe5252a2966e26b8cb4c834a4ae40/agent/prompts/raw/p_cot_id_actree_2s.py#L34
        if self.with_homepage_hint:
            goal += f"""

(Note: if you want to visit other websites, check out the homepage at {self.webarena_instance.home_url}. It has a list of websites you can visit. {self.webarena_instance.home_url}/password.html lists all the account name and password for the websites. You can use them to log in to the websites.)
"""

        # This note is present in some of webarena's agent prompts
        if self.with_na_hint:
            goal += """\

If you believe the task is impossible to complete, provide the answer "N/A".
"""

        return goal, {}

    def cheat(self, page: playwright.sync_api.Page, chat_messages: list[str]) -> None:
        raise NotImplementedError

    @classmethod
    def get_task_id(cls):
        """
        Generic class for several task ids, this way of obtaining the task id is not compatible for now.
        """
        raise NotImplementedError

    def teardown(self) -> None:
        # Nothing to be done here
        # https://github.com/web-arena-x/webarena/blob/c6475f0e9affe5252a2966e26b8cb4c834a4ae40/browser_env/envs.py#L227

        with open(
            os.path.join(
                self.study_dir,
                "nudge_metadata.yaml"
            ),
            "w"
        ) as yaml_file:
            yaml.dump(self.nudge_metadata, yaml_file)

    def validate(
        self, page: playwright.sync_api.Page, chat_messages: list[str]
    ) -> tuple[float, bool, str, dict]:

        # safeguard: check that all open tabs are either blank or within the list of WebArena URLs
        authorized_locations = ["newtab", ""] + [
            urllib.parse.urlparse(url).netloc
            for url in [*self.webarena_instance.urls.values(), self.webarena_instance.home_url]
        ]
        for open_page in page.context.pages:
            page_location = urllib.parse.urlparse(open_page.url).netloc
            if not page_location in authorized_locations:
                return 0, True, "", {"error": "Unauthorized url, terminating task"}

        # import webarena dynamically
        from webarena.browser_env.actions import ActionTypes

        # if any, use the last assistant message as the stop answer for webarena
        if chat_messages and chat_messages[-1]["role"] == "assistant":
            last_action = {"action_type": ActionTypes.STOP, "answer": chat_messages[-1]["message"]}
        elif chat_messages and chat_messages[-1]["role"] == "infeasible":
            last_action = {"action_type": ActionTypes.STOP, "answer": "N/A"}
        else:
            last_action = {"action_type": ActionTypes.NONE, "answer": ""}
            # llm_fuzzy_match() bugfix
            last_action["answer"] = "whatever"

        # hack: fake trajectory for evaluation (only last_action["answer"] is used in the webarena evaluation codebase)
        trajectory = [{}, last_action]  # StateInfo, Action

        # call the evaluator
        try:
            score = self.evaluator(
                trajectory=trajectory,
                config=self.config,
                page=page,
                client=None,  # none of webarena's evaluators requires a cdp session
            )
        # llm_fuzzy_match() bugfix (assert "correct" in response)
        except AssertionError:
            logger.debug(
                "llm_fuzzy_match() bugfix applied: AssertionError in evaluator, using score = 0.0"
            )
            score = 0.0

        if score > 0 or last_action["action_type"] == ActionTypes.STOP:
            return score, True, "", {}
        else:
            return score, False, "", {}

    def process_html(self, html: str) -> str:
        """
        Do any task-specific processing of the page's underlying content here.

        This will be called by nudgelab.browser.NudgeLabBrowserEnv in the route handler.
        """
        return html


class NudgeLabShopTask(NudgeLabTask):
    """
    NudgeLabShopTask is a subclass of NudgeLabTask that implements some extra logic for the shop task.
    """

    def process_html(self, html: str) -> str:

        soup = BeautifulSoup(html, "lxml")

        if soup.find("meta", property="og:type", content="product"):
            # Page type is product
            return product_rating(html)

        if soup.select_one("div.sidebar-main div.filter"):
            # Page type is category
            return category_rating(html)

        if soup.title and soup.title.string.strip() == "One Stop Market":
            # Page type is home
            return home_rating(html)

        return html
