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
    "nudgingarena.DefaultProductQuantity-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_default_product_quantity.json")},
)

register_task(
    "nudgingarena.ShippingExample-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "shipping_example.json")},
)

register_task(
    "nudgingarena.TestProductRating-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_product_rating.json")},
)


register_task(
    "nudgingarena.TestProductReviews-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_product_reviews.json")},
)


register_task(
    "nudgingarena.TestShopDescription-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_shop_description.json")},
)


register_task(
    "nudgingarena.TestShopPricing-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_shop_pricing.json")},
)


register_task(
    "nudgingarena.TestShopTitle-v0",
    task.GenericWebArenaTask,
    task_kwargs={"config_file": str(Path(__file__).parent.parent.parent / "nudgingarena" / "config_files" / "test_shop_title.json")},
)



