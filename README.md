## Setup AgentLab+NudgingArena

AgentLab requires python 3.11 or 3.12.

```bash
git submodule update --init --recursive
```

```bash
pip install -r requirements.txt
```

```bash
pip install -e ./nudgingarena ./agentlab
```

Equivalently, you can use `uv pip …` for the above commands (preferred), if you first `pip install uv`.

If not done already, install Playwright:
```bash
playwright install
```

Next, you will need a `.env` file with these vars:
```bash
WA_SHOPPING="<URL>"
WA_SHOPPING_ADMIN="<URL>"
WA_REDDIT="<URL>"
WA_GITLAB="<URL>"
WA_WIKIPEDIA="<URL>"
WA_MAP="<URL>"
WA_HOMEPAGE="<URL>"
AGENTLAB_EXP_ROOT="agent_lab_exp"
OPENAI_API_KEY="<KEY>"
```

If you're only running one environment, you can set the other `WA_` URLs to the same one to avoid errors at runtime.

Test run with the nudgingarena benchmark.
```bash
python agent_lab_run.py
```

If you are on a remote server, you can try the following command to run the experiment.
```bash
xvfb-run python agent_lab_run.py
```

### AgentXray

https://github.com/user-attachments/assets/06c4dac0-b78f-45b7-9405-003da4af6b37

Make sure that you have 'agentlab-xray = analyze.agent_xray:main' in the agenlab/agentlab.egg-info/entry_points.txt file.


In a terminal, execute:
```bash
export AGENTLAB_EXP_ROOT=<root directory of experiment results>  # Should likely be ./agent_lab_exp
agentlab-xray
```

You can load previous or ongoing experiments in the directory `AGENTLAB_EXP_ROOT` and visualize the results in a gradio interface.

In the following order, select:
* The experiment you want to visualize
* The agent if there is more than one
* The task
* And the seed

Once this is selected, you can see the trace of your agent on the given task. Click on the profiling
image to select a step and observe the action taken by the agent.
