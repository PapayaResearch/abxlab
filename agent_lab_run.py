import logging
import dotenv
import hydra
import typing
import browsergym.experiments.benchmark.base

browsergym.experiments.benchmark.base.BenchmarkBackend = typing.Literal[
    "miniwob", "webarena", "visualwebarena", "workarena",
    "assistantbench", "weblinx", "nudgingarena"
]

from browsergym.core.registration import register_task
from omegaconf import OmegaConf, DictConfig
from agentlab.experiments.study import Study
from browsergym.experiments.loop import EnvArgs
from nudge_task import NudgingArenaTask


# Load all env vars
dotenv.load_dotenv()


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig):
    logging.basicConfig(level=cfg.experiment.logging_level_stdout, format='%(levelname)s:%(name)s:%(message)s')
    log = logging.getLogger(__name__)

    agent = hydra.utils.instantiate(cfg.agent)
    benchmark = hydra.utils.instantiate(cfg.benchmark, _partial_=True)(
        # Necessary workaround for now, to avoid Union instantiation OmegaConf issues
        env_args_list=[
            EnvArgs(**item) for item in cfg.benchmark.env_args_list
        ]
    )

    # Register the env here, so we don't need to reach into BrowserGym
    register_task(
        id=f"nudgingarena.{cfg.task.name}",
        task_class=NudgingArenaTask,
        task_kwargs=OmegaConf.to_container(cfg.task, resolve=True)
    )

    study = Study(
        agent_args=[agent],
        benchmark=benchmark,
        logging_level_stdout=cfg.experiment.logging_level_stdout
    )

    log.info("Running experiment…")
    study.run(
        n_jobs=cfg.experiment.n_jobs,
        parallel_backend=cfg.experiment.parallel_backend,
        n_relaunch=cfg.experiment.n_relaunch
    )
    log.info("Experiment finished.")


if __name__ == "__main__":
    main()
