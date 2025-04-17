import nltk
import os
from pathlib import Path

from browsergym.core.registration import register_task

from . import config, task

# download necessary tokenizer resources
# note: deprecated punkt -> punkt_tab https://github.com/nltk/nltk/issues/3293
try:
    nltk.data.find("tokenizers/punkt_tab")
except:
    nltk.download("punkt_tab", quiet=True, raise_on_error=True)

# # Register task using webarena-style format
# task_id = "nudgingarena.shopping-v0"  # Use dot notation like webarena.{task_id}

# print("Registering nudgingarena task")

# config_path = Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_shop.json"
# print(f"Looking for config file at: {config_path}")

# # Register nudging arena task with config
# register_task(
#     task_id,
#     task.GenericWebArenaTask,
#     task_kwargs={"config_file": str(config_path)},
# )

# print("nudgingarena task registered")


register_task(
    "nudgingarena.BestsellerProduct-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_bestseller_product.json")},
)
