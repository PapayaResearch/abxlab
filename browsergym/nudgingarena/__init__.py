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

# register all NudgingArena benchmark
register_task(
    "nudgingarena.BestsellerProduct-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_bestseller_product.json")},
)
