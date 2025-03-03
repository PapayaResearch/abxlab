import importlib.resources
import nudgingarena

# Get path to config file in the nudgingarena package
CONFIG_FILE = str(importlib.resources.files(nudgingarena).joinpath("config_files/test_shop.json"))

# Remove task IDs since we're not using them
# TASK_IDS = [276]  # Remove this
