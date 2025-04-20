import os
import logging

from agentlab.agents.generic_agent import (
    AGENT_LLAMA3_70B,
    AGENT_LLAMA31_70B,
    RANDOM_SEARCH_AGENT,
    AGENT_4o,
    AGENT_4o_MINI,
    AGENT_o3_MINI,
    AGENT_o1_MINI,
    AGENT_37_SONNET,
    AGENT_CLAUDE_SONNET_35,
)
from agentlab.experiments.study import Study

AGENT_ARGS = [AGENT_4o_MINI]
BENCHMARK = "nudgingarena_tiny"

def main():
    logging.getLogger().setLevel(logging.INFO)

    os.environ["AGENTLAB_EXP_ROOT"] = os.path.abspath("agent_lab_exp")

    os.environ[
        "WA_SHOPPING"
    ] = "http://matlaber12.media.mit.edu:7770/"

    study = Study(
        AGENT_ARGS,
        BENCHMARK,
        logging_level_stdout=logging.WARNING
    )

    study.run(
        n_jobs=1,
        parallel_backend="ray",
        n_relaunch=1
    )

if __name__ == '__main__':
    # The code needs to be inside this to avoid issues with multiprocessing in macOS
    main()
