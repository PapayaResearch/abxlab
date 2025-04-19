import os
from agentlab.agents.generic_agent import AGENT_4o_MINI, AGENT_3_5
from agentlab.experiments.study import make_study

def main():
    os.environ["AGENTLAB_EXP_ROOT"] = os.path.abspath("agent_lab_exp")

    os.environ[
        "WA_SHOPPING"
    ] = "http://matlaber12.media.mit.edu:7770/"

    # # if your webarena instance offers the FULL_RESET feature (optional)
    # os.environ["WA_FULL_RESET"] = f"{BASE_URL}:7565"

    # # otherwise, be sure to NOT set WA_FULL_RESET, or set it to an empty string
    # os.environ["WA_FULL_RESET"] = ""

    study = make_study(
        benchmark="nudgingarena_tiny",  # or "webarena", "workarena_l1" ...
        agent_args=[AGENT_4o_MINI],
        comment="test with nudgingarena",
    )

    study.run(n_jobs=1)

if __name__ == '__main__':
    # The code needs to be inside this to avoid issues with multiprocessing in macOS
    main()
