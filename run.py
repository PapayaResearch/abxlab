import os
import glob
import datetime
import logging
import json
import dotenv
dotenv.load_dotenv()
os.environ["AGENTLAB_EXP_ROOT"] = os.path.join( # Make unique run directory (mainly for gathering multiruns)
    os.environ["AGENTLAB_EXP_ROOT"],
    datetime.datetime.now().strftime("run-%Y-%m-%d_%H-%M-%S")
)
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

    # Check if we want to continue a previous experiment set
    study_dir = (Path(cfg.experiment.root_dir) / cfg.task.name).absolute()
    if cfg.experiment.continue_from:
        study_dir_from_prev = (Path(cfg.experiment.continue_from) / cfg.task.name).absolute()
        if study_dir_from_prev.exists():
            # Check if the experiment ran *correctly*
            summary_info = glob.glob(os.path.join(study_dir_from_prev, "**", "*", "summary_info.json"), recursive=True)
            assert len(summary_info) == 1, "There should be exactly one summary_info.json file"
            with open(summary_info[0]) as json_file:
                summary_info = json.load(json_file)

            if (summary_info["err_msg"] is None) and (summary_info["stack_trace"] is None):
                log.info("Skipping %s; it seems to have run correctly.", cfg.task.name)
                return 0
            else:
                log.info("Re-running %s; it seems to have run incorrectly.", cfg.task.name)

    # Instantiate agent and benchmark directly from Hydra configs
    agent = hydra.utils.instantiate(cfg.agent)
    benchmark = hydra.utils.instantiate(cfg.benchmark, _partial_=True)(
        # Necessary workaround for now, to avoid Union instantiation OmegaConf issues
        env_args_list=[
            EnvArgs(**item) for item in cfg.benchmark.env_args_list
        ]
    )

    # Register the env here, so we don't need to reach into BrowserGym
    study_dir = (Path(cfg.experiment.root_dir) / cfg.task.name).absolute()
    gym.register(
        id=f"browsergym/nudgelab.{cfg.task.name}",
        entry_point=lambda *env_args, **env_kwargs: NudgeLabBrowserEnv(
            task_entrypoint=getattr(
                nudgelab.task,
                cfg.task.entrypoint.replace("nudgelab.task.", "")
            ),
            task_kwargs={
                **OmegaConf.to_container(cfg.task, resolve=True),
                "study_dir": study_dir
            }
        ),
        nondeterministic=True
    )

    study_dir = (Path(cfg.experiment.root_dir) / cfg.task.name).absolute()

    study = Study(
        agent_args=[agent],
        benchmark=benchmark,
        logging_level_stdout=cfg.experiment.logging_level_stdout,
        dir=study_dir
    )

    log.info("Running experiment…")
    study.run(
        n_jobs=cfg.experiment.n_jobs,
        parallel_backend=cfg.experiment.parallel_backend,
        n_relaunch=cfg.experiment.n_relaunch
    )
    log.info("Experiment finished.")

    OmegaConf.save(
        cfg,
        os.path.join(study_dir, "config.yaml"),
        resolve=True
    )

    return 0


if __name__ == "__main__":
    main()
