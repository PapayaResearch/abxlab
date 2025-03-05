import os

os.environ["AGENTLAB_EXP_ROOT"] = os.path.abspath("agent_lab_exp")

os.environ[
    "WA_SHOPPING"
] = "http://matlaber12.media.mit.edu:7770/"
os.environ[
    "WA_SHOPPING_ADMIN"
] = "http://ec2-3-131-244-37.us-east-2.compute.amazonaws.com:7780/admin"
os.environ[
    "WA_REDDIT"
] = "http://ec2-3-131-244-37.us-east-2.compute.amazonaws.com:9999"
os.environ[
    "WA_GITLAB"
] = "http://ec2-3-131-244-37.us-east-2.compute.amazonaws.com:8023"
os.environ[
    "WA_MAP"
] = "http://ec2-3-131-244-37.us-east-2.compute.amazonaws.com:3000"
os.environ[
    "WA_WIKIPEDIA"
] = "http://ec2-3-131-244-37.us-east-2.compute.amazonaws.com:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
os.environ[
    "WA_HOMEPAGE"
] = "PASS"  # The home page is not currently hosted in the demo site

# # if your webarena instance offers the FULL_RESET feature (optional)
# os.environ["WA_FULL_RESET"] = f"{BASE_URL}:7565"

# # otherwise, be sure to NOT set WA_FULL_RESET, or set it to an empty string
# os.environ["WA_FULL_RESET"] = ""

from agentlab.agents.generic_agent import AGENT_4o_MINI, AGENT_3_5

from agentlab.experiments.study import make_study

study = make_study(
    benchmark="nudgingarena_tiny",  # or "webarena", "workarena_l1" ...
    agent_args=[AGENT_4o_MINI],
    # agent_args=[AGENT_3_5],
    comment="test with nudgingarena",
)

study.run(n_jobs=1,n_relaunch=3)