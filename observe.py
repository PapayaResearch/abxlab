import os
import logging
import dotenv
dotenv.load_dotenv()
import hydra
import yaml
from pathlib import Path
from omegaconf import OmegaConf, DictConfig
from nudgelab.browser import NudgeLabBrowserEnv
from nudgelab.task import StaticPageTask


@hydra.main(config_path="conf/experiment", config_name="exp1242", version_base="1.3")
def main(cfg: DictConfig):
    
    
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

    def save_as_mhtml(page, url_dir, filename):
        """Save page as MHTML format which includes all resources"""
        cdp = page.context.new_cdp_session(page)
        mhtml = cdp.send("Page.captureSnapshot", {})
        mhtml_path = url_dir / f"{filename}.mhtml"
        with open(mhtml_path, "w", encoding="utf-8") as f:
            f.write(mhtml["data"])
        return mhtml_path

    # Process all start_urls
    if "start_urls" in task_config:
        for start_url in task_config["start_urls"]:
            relative_url = start_url.replace("${env.wa_shopping_url}", "")
            url = base_url + relative_url
            log.info(f"Processing start URL: {url}")
            
            # Create directory for this URL
            url_dir = output_dir / relative_url.replace("://", "_").replace("/", "_").replace(".", "_")
            url_dir.mkdir(parents=True, exist_ok=True)
            
            if relative_url not in modified_urls:
                env = NudgeLabBrowserEnv(
                    task_entrypoint=StaticPageTask,
                    task_kwargs={"url": url, "config": {}},
                    headless=True,
                    timeout=100000
                )
                env.reset()
                
                env.page.screenshot(
                    path=str(url_dir / "original_screenshot.png"),
                    full_page=True,
                    scale="device"
                )
                with open(url_dir / "original_page.html", "w", encoding="utf-8") as f:
                    f.write(env.page.content())

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
            headless=True,
            timeout=100000
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