import os
import logging
import dotenv
dotenv.load_dotenv()
import hydra
import gymnasium as gym
from omegaconf import OmegaConf, DictConfig
from agentlab.experiments.study import Study
from browsergym.experiments.loop import EnvArgs
from nudgelab.browser import NudgeLabBrowserEnv
from nudgelab.task import NudgeLabTask


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig):
    logging.basicConfig(level=cfg.experiment.logging_level_stdout, format='%(levelname)s:%(name)s:%(message)s')
    log = logging.getLogger(__name__)

    # Instantiate agent and benchmark directly from Hydra configs
    agent = hydra.utils.instantiate(cfg.agent)
    benchmark = hydra.utils.instantiate(cfg.benchmark, _partial_=True)(
        # Necessary workaround for now, to avoid Union instantiation OmegaConf issues
        env_args_list=[
            EnvArgs(**item) for item in cfg.benchmark.env_args_list
        ]
    )

    # Register the env here, so we don't need to reach into BrowserGym
    gym.register(
        id=f"browsergym/nudgelab.{cfg.task.name}",
        entry_point=lambda *env_args, **env_kwargs: NudgeLabBrowserEnv(
            task_entrypoint=NudgeLabTask,
            task_kwargs=OmegaConf.to_container(cfg.task, resolve=True)
        ),
        nondeterministic=True
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

    # Store config in the experiment directory for analysis
    OmegaConf.save(
        cfg,
        os.path.join(study.dir, "config.yaml"),
        resolve=True
    )


if __name__ == "__main__":
    main()
