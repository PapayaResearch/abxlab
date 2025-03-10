import importlib.resources
import nudgingarena

# Get path to config file in the nudgingarena package
CONFIG_FILE = str(importlib.resources.files(nudgingarena).joinpath("config_files/test_shop.json"))


