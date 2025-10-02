# ABxLab: A Framework for Studying AI Agent Behavior

![Python version](https://img.shields.io/badge/python-3.11-blue)
![Package version](https://img.shields.io/badge/version-0.1.0-green)
![GitHub license](https://img.shields.io/github/license/PapayaResearch/abxlab)

> [!NOTE]
> Code for the paper **[A Framework for Studying AI Agent Behavior: Evidence from Consumer Choice Experiments](https://arxiv.org/abs/2509.25609)**.

Environments built for people are increasingly operated by a new class of economic actors: **LLM-powered software agents** making decisions on our behalf. These decisions range from our purchases to travel plans to medical treatment selection. Current evaluations of these agents largely focus on task competence, but we argue for a deeper assessment: *how* these agents choose when faced with realistic decisions. We introduce **ABxLab**, a **framework for systematically probing agentic choice** through controlled manipulations of option attributes and persuasive cues. We apply this to a **realistic web-based shopping environment**, where we vary prices, ratings, and psychological nudges, all of which are factors long known to shape human choice.

## Features

- 📊 Configurable A/B testing with interventions and preferences for any website
- 🤖 Support for multiple LLM agents through various providers (e.g. LiteLLM)
- 🛒 E-commerce shopping task environment with realistic browsing scenarios
- 🔍 AgentXray visualization tool for debugging agent behavior
- ⚙️ Hydra-based configuration system for reproducible experiments

## Prerequisites

- Python 3.11 or 3.12
- Node.js and npm (for Playwright)
- R (optional, for statistical analysis)

## Installation

### 1. Install Python Dependencies

```bash
conda create -n abxlab python=3.11
conda activate abxlab
```

Using pip:
```bash
pip install -r requirements.txt
cd ./agentlab && pip install -e . && cd ..
```

Or using `uv` (recommended for faster installs):
```bash
pip install uv
uv pip install -r requirements.txt
cd ./agentlab && uv pip install -e . && cd ..
```

### 2. Install Playwright

Playwright is required for browser automation:
```bash
playwright install
```

### 3. [Optional] Install DSPy

In a few `scripts` we use [DSPy](https://dspy.ai/), but it conflicts with `hydra-ray-launcher` so you can install it separately:

```bash
pip install dspy==2.6.27
```

### 3. Configure Environment Variables

Create a `.env` file in the project root with the following configuration:

> [!IMPORTANT]
> Due to AgentLab and BrowserGym dependencies, you must set all these endpoints to avoid runtime errors. We don't host WebArena environments, but you can deploy them following these [instructions](https://github.com/web-arena-x/webarena/blob/main/environment_docker/README.md).

```bash
# Base URL for web agent environments
BASE_WEB_AGENT_URL="<YOUR_SERVER_URL>"

# Primary Endpoints (can point to different environments)
SHOPPING="${BASE_WEB_AGENT_URL}"
SHOPPING_ADMIN="${BASE_WEB_AGENT_URL}"
REDDIT="${BASE_WEB_AGENT_URL}"
GITLAB="${BASE_WEB_AGENT_URL}"
WIKIPEDIA="${BASE_WEB_AGENT_URL}"
MAP="${BASE_WEB_AGENT_URL}"
HOMEPAGE="${BASE_WEB_AGENT_URL}"

# Synced WA_ Prefixed Vars (required by BrowserGym)
WA_SHOPPING="${SHOPPING}"
WA_SHOPPING_ADMIN="${SHOPPING_ADMIN}"
WA_REDDIT="${REDDIT}"
WA_GITLAB="${GITLAB}"
WA_WIKIPEDIA="${WIKIPEDIA}"
WA_MAP="${MAP}"
WA_HOMEPAGE="${HOMEPAGE}"

# Results will be saved in this directory
AGENTLAB_EXP_ROOT="results"

# LLM API Keys (add only the ones you plan to use)
OPENAI_API_KEY="<YOUR_OPENAI_KEY>"
ANTHROPIC_API_KEY="<YOUR_ANTHROPIC_KEY>"
GEMINI_API_KEY="<YOUR_GEMINI_KEY>"
AWS_REGION_NAME="<AWS_REGION>"
AWS_ACCESS_KEY_ID="<AWS_ACCESS_KEY_ID>"
AWS_SECRET_ACCESS_KEY="<YOUR_AWS_KEY>"
```

## Running Experiments

> [!NOTE]
> Results are saved to `AGENTLAB_EXP_ROOT` defined in the `.env` above.

> [!TIP]
> The results contain the raw data. You can adapt `scripts/collect_results.py`, which transforms results into a CSV file that is easier to analyze.

### Defining the Environment

The main configuration file `conf/config.yaml` defines the `abxlab_url` used throughout the codebase. By default, we choose one of the variables defined in `.env` above, but you can replace it.

```yaml
env:
  abxlab_url: ${oc.env:WA_SHOPPING}
```

### Running Your First Experiment

The easiest way to run `ABxLab` is with a configuration file like the example in `ABxLab/conf/task/test/basic.yaml`. This works out of the box if you set `BASE_WEB_AGENT_URL="https://www.amazon.com/"` in `.env`, and it's easy to adapt!

- `start_urls`: This defines the URLs the agent will see. In this example, the homepage.
- `intent_template`: This defines the goal of the task. In this example, searching for a "toy papaya".
- `choices`: This defines all intervention functions. In this case, it includes a nudge below the product title.
- `eval`: This defines the stopping condition. In this example, once a product is added to the cart.

```bash
python run.py task=test/basic
```

You can visualize the results with [AgentXray](#agentxray-visualizing-results).

### Scaling Experiments

There are other useful ways of running experiments. For example, you can also run any of the experiments in `conf/` as:

```bash
python run.py +experiment-regular=exp10
```

For more elaborated experiments, you can generate all configurations programmatically. In the shopping environment, the script `scripts/generate_experiments.py` generates experiment configurations in `--exp-dir` from the data in `tasks/`:

```bash
python scripts/generate_experiments.py --match-price --match-review-count --products=tasks/product_pairs-matched-ratings.csv --exp-dir conf/experiment
```

Then, one can run all these experiments with multirun

```bash
# Define the range of experiment IDs you want to run (e.g., exp0 through N)
N=100
EXPS=$(echo exp{0..$N} | tr ' ' ',')
python run.py --multirun "+experiment=${EXPS}"
```

> [!WARNING]
> Multirun can generate very large files because AgentLab prints out all uncommitted files in the directory. Consider including them in .gitignore to avoid these issues.

### Customizing Experiments with Hydra

`ABxLab` uses [Hydra](https://hydra.cc/) for configuration management. You can override any configuration parameter from the command line.

#### Select a Different LLM

Supported models and providers are in `conf/agent/`, which can be easily extended. We use [LiteLLM](https://www.litellm.ai/) by default, but you can find more details below.

```bash
# Use GPT 5
python run.py agent=gpt-5

# Use Claude 4.5 Sonnet
python run.py agent=claude-4-5-sonnet

# Use Gemini 2.5 Pro
python run.py agent=gemini-2-5-pro

# Use DeepSeek R1
python run.py agent=deepseek-r1
```

### Advanced Usage & Customization

### Project Structure

```
ABxLab/
├── abxlab/              # Core ABxLab modules
│   ├── actions.py       # Custom agent action definitions
│   ├── browser.py       # Custom browser env to execute intervention functions
│   ├── evaluators.py    # Custom task evaluation logic
│   ├── task.py          # Custom task definitions
│   └── choices/         # Intervention functions for each environment
├── agentlab/            # Modified version of AgentLab
├── analysis/            # R scripts for statistical analysis
├── conf/                # Hydra configuration files
│   ├── agent/           # Agent configurations (GPT, Claude, etc.)
│   ├── benchmark/       # Benchmark configurations
│   ├── task/            # Task configurations
│   └── config.yaml      # Main config file
├── scripts/             # Scripts for generating experiments, collecting results, etc
│   ├── generate_experiments.py
│   ├── collect_results.py
│   └── ...
├── tasks/               # Data for generating experiments
│   ├── products.csv
│   ├── interventions.csv
│   └── ...
├── run.py               # Main experiment runner
└── requirements.txt     # Python dependencies
```

### Tasks

You can create new tasks in `conf/task/` and use `shopping.yaml` or `test/basic.yaml` as inspiration. Most of this logic is inherited from [WebArena](https://github.com/web-arena-x/webarena), so we refer the reader there for details. We modify it with:

- `entrypoint: abxlab.task.ABxLabShopTask`: This is a custom class where we run logic that we always need for the shopping environment. Otherwise, you can use its parent `entrypoint: abxlab.task.ABxLabTask`.
- `config.choices`: This is a placeholder, which you can copy and paste. Your configs (e.g. conf/task/test) should inherit this config, and you can replace `choices` with either an empty list (no interventions needed) or a list of functions following the details below.

We also define our own `config.eval`, which is a stopping condition.

### Interventions

ABxLab allows you to define a set of intervention functions in the configurations. If an agent visits a matching URL, then all functions get executed sequentially. Each function receives the HTML (by default) and a set of arguments defined in the configuration file. The field `nudge` can be used as an identifier to recognize during analysis. You can see an example [here](https://github.com/PapayaResearch/AgentLab/blob/main/conf/task/test/bestseller_product.yaml).

### Benchmark

The ABxLab [benchmark](https://github.com/PapayaResearch/AgentLab/blob/main/conf/benchmark/abxlab.yaml) can be used as is in most cases. It's worth noting that here is where we define the high level actions available for agents, which we customized [here](https://github.com/PapayaResearch/AgentLab/blob/967c3d1e2c064b988f4b14744b7a6ffb75269945/abxlab/actions.py#L203-L212) to remove unnecessary actions available in BrowserGym.

### Agent

You can see the agent's default flags [here](https://github.com/PapayaResearch/AgentLab/blob/main/conf/agent/flags/default.yaml). You can see more details in [AgentLab](https://github.com/ServiceNow/AgentLab/), but here you can decide whether to use thinking, memory, pruned HTML or accessibility trees, etc.

### LLM Providers

We included support for [LiteLLM](https://www.litellm.ai/) and set it by default in all agent configurations in `conf/agent/`. However, there are other options available like OpenRouter that you can see [here](https://github.com/PapayaResearch/AgentLab/blob/main/agentlab/llm/chat_api.py).

## AgentXray: Visualizing Results

AgentXray is a Gradio-based visualization tool by [AgentLab](https://github.com/ServiceNow/AgentLab) for debugging and analyzing agent behavior.

https://github.com/user-attachments/assets/06c4dac0-b78f-45b7-9405-003da4af6b37

Export the environment variable to specify the path for the results, and then launch AgentXray

```bash
export AGENTLAB_EXP_ROOT=./results
agentlab-xray
```

## FAQs

### Can I access the data from the experiments in the paper?

Reach out to us! We have hundreds of GBs of data.

## Citing & Acknowledgements

If you use `ABxLab` in your research, please cite the following paper:
```bibtex
@article{cherep2025framework,
 title={A Framework for Studying AI Agent Behavior: Evidence from Consumer Choice Experiments},
 author={Manuel Cherep and Chengtian Ma and Abigail Xu and Maya Shaked and Pattie Maes and Nikhil Singh},
 year={2025},
 url={https://arxiv.org/abs/2509.25609},
}
```

Research reported in this publication was supported by an Amazon Research Award, Fall 2024. We also received funding from SK Telecom in partnership with the MIT Generative AI Impact Consortium (MGAIC). Experiments conducted in this paper were generously supported via API credits provided by OpenAI, Anthropic, and Google. MC is supported by a fellowship from “la Caixa” Foundation (ID 100010434) with code LCF/BQ/EU23/12010079.

This project builds on [AgentLab](https://github.com/ServiceNow/AgentLab) and [BrowserGym](https://github.com/ServiceNow/BrowserGym), for which we are thankful.
