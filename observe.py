import os
import logging
import dotenv
import hydra
import yaml
from pathlib import Path
from omegaconf import OmegaConf, DictConfig
from nudgelab.browser import NudgeLabBrowserEnv
from nudgelab.task import StaticPageTask


@hydra.main(config_path="conf/experiment", config_name="exp2067", version_base="1.3")
def main(cfg: DictConfig):
    dotenv.load_dotenv()
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    logging.getLogger("bs4.dammit").setLevel(logging.CRITICAL)
    log = logging.getLogger(__name__)

    exp_name = hydra.core.hydra_config.HydraConfig.get().job.config_name
    
    output_base = Path("human_observation")
    output_dir = output_base / exp_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the config file for reference
    config_save_path = output_dir / "config.yaml"
    OmegaConf.save(cfg, config_save_path)

    # using hard-coded workaround to get base URL
    base_url = os.getenv('WA_SHOPPING', 'http://matlaber12.media.mit.edu:7770/')
    if not base_url.endswith('/'):
        base_url += '/'

    task_config = OmegaConf.to_container(cfg.task.config)
    
    # Get URLs that will be modified (from choices)
    modified_urls = set()
    for choice in task_config["choices"]:
        relative_url = choice["url"].replace("${env.wa_shopping_url}", "")
        modified_urls.add(relative_url)

    # start_urls that aren't in choices (original content only)
    if "start_urls" in task_config:
        for start_url in task_config["start_urls"]:
            relative_url = start_url.replace("${env.wa_shopping_url}", "")
            if relative_url in modified_urls:
                continue  # Skip if in choices
            url = base_url + relative_url
            log.info(f"Processing start URL: {url}")
            
            # Create directory for this URL
            url_dir = output_dir / relative_url.replace("://", "_").replace("/", "_").replace(".", "_")
            url_dir.mkdir(parents=True, exist_ok=True)

            # Capture original content 
            env = NudgeLabBrowserEnv(
                task_entrypoint=StaticPageTask,
                task_kwargs={"url": url, "config": {}},
                headless=True
            )
            env.reset()
            
            env.page.screenshot(
                path=str(url_dir / "original_screenshot.png"),
                full_page=True,
                scale="device"
            )
            with open(url_dir / "original_page.html", "w", encoding="utf-8") as f:
                f.write(env.page.content())
            
            env.browser.close()

    # choices URLs (modified content only)
    for choice in task_config["choices"]:
        relative_url = choice["url"].replace("${env.wa_shopping_url}", "")
        url = base_url + relative_url
        choice["url"] = url
        
        url_dir = output_dir / relative_url.replace("://", "_").replace("/", "_").replace(".", "_")
        url_dir.mkdir(parents=True, exist_ok=True)

        # Capture modified content
        env = NudgeLabBrowserEnv(
            task_entrypoint=StaticPageTask,
            task_kwargs={"url": url, "config": task_config},
            headless=True
        )
        env.reset()
        
        env.page.screenshot(
            path=str(url_dir / "modified_screenshot.png"),
            full_page=True,
            scale="device"
        )
        with open(url_dir / "modified_page.html", "w", encoding="utf-8") as f:
            f.write(env.page.content())

        env.browser.close()


if __name__ == "__main__":
    main() 