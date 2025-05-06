## Setup NudgeLab

NudgeLab requires python 3.11 or 3.12.

```bash
pip install -r requirements.txt
cd ./agentlab && pip install -e . && cd ..
```

Equivalently, you can use `uv pip …` for the above commands (preferred), if you first `pip install uv`.

If not done already, install Playwright:
```bash
playwright install
```

Next, you will need a `.env` file with these vars:
```bash
BASE_WEB_AGENT_URL="<URL>"

# Primary Endpoints
SHOPPING="${BASE_WEB_AGENT_URL}"
SHOPPING_ADMIN="${BASE_WEB_AGENT_URL}"
REDDIT="${BASE_WEB_AGENT_URL}"
GITLAB="${BASE_WEB_AGENT_URL}"
WIKIPEDIA="${BASE_WEB_AGENT_URL}"
MAP="${BASE_WEB_AGENT_URL}"
HOMEPAGE="${BASE_WEB_AGENT_URL}"

# Synced WA_ Prefixed Vars (these are necessary for BrowserGym)
WA_SHOPPING="${SHOPPING}"
WA_SHOPPING_ADMIN="${SHOPPING_ADMIN}"
WA_REDDIT="${REDDIT}"
WA_GITLAB="${GITLAB}"
WA_WIKIPEDIA="${WIKIPEDIA}"
WA_MAP="${MAP}"
WA_HOMEPAGE="${HOMEPAGE}"

# Other Configurations
AGENTLAB_EXP_ROOT="results"
OPENAI_API_KEY="<KEY>"
```

If you're only running one environment, you can set the other `WA_` URLs to the same one to avoid errors at runtime.

Test run with the nudgingarena benchmark.
```bash
python run.py
```

If you are on a remote server, you can try the following command to run the experiment.
```bash
xvfb-run python run.py
```

### Download Data

In order to generate the experiment configs, you need to download our data. To do so, you can run `scripts/download_data.sh` and need to set a Google token (which you can generate [here](https://developers.google.com/oauthplayground/))

```bash
export GOOGLE_TOKEN=<YOUR TOKEN>
```

### AgentXray

https://github.com/user-attachments/assets/06c4dac0-b78f-45b7-9405-003da4af6b37

Make sure that you have 'agentlab-xray = analyze.agent_xray:main' in the agenlab/agentlab.egg-info/entry_points.txt file.


In a terminal, execute:
```bash
export AGENTLAB_EXP_ROOT=<root directory of experiment results>  # Should likely be ./results
agentlab-xray
```

To avoid re-exporting `AGENTLAB_EXP_ROOT`, you can also do:
```bash
set -a && source .env
agentlab-xray
set +a # Optional, to turn off the allexport
```

You can load previous or ongoing experiments in the directory `AGENTLAB_EXP_ROOT` and visualize the results in a gradio interface.

In the following order, select:
* The experiment you want to visualize
* The agent if there is more than one
* The task
* And the seed

Once this is selected, you can see the trace of your agent on the given task. Click on the profiling
image to select a step and observe the action taken by the agent.
