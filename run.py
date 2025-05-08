import os
import datetime
import logging
import dotenv
dotenv.load_dotenv()
os.environ["AGENTLAB_EXP_ROOT"] = os.path.join(os.environ["AGENTLAB_EXP_ROOT"], datetime.datetime.now().strftime("run-%Y-%m-%d_%H-%M-%S"))
import hydra
import gymnasium as gym
import nudgelab.task
from pathlib import Path
from omegaconf import OmegaConf, DictConfig
from agentlab.experiments.study import Study
from browsergym.experiments.loop import EnvArgs
from nudgelab.browser import NudgeLabBrowserEnv


@hydra.main(config_path="conf", config_name="config", version_base="1.3")
def main(cfg: DictConfig):
    logging.basicConfig(level=cfg.experiment.logging_level_stdout, format='%(levelname)s:%(name)s:%(message)s')
    logging.getLogger("bs4.dammit").setLevel(logging.CRITICAL)
    log = logging.getLogger(__name__)

    # Avoid LiteLLM extremely long logs
    os.environ["LITELLM_LOG"] = "INFO"

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
            task_entrypoint=getattr(
                nudgelab.task,
                cfg.task.entrypoint.replace("nudgelab.task.", "")
            ),
            task_kwargs=OmegaConf.to_container(cfg.task, resolve=True)
        ),
        nondeterministic=True
    )

    study = Study(
        agent_args=[agent],
        benchmark=benchmark,
        logging_level_stdout=cfg.experiment.logging_level_stdout,
        dir=Path(cfg.experiment.root_dir).absolute()
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
        os.path.join(cfg.experiment.exp_dir, "config.yaml"),
        resolve=True
    )


if __name__ == "__main__":
    main()
