import os
import asyncio
from playwright.async_api import async_playwright
from config import settings
from services.storage import generate_short_id

async def capture_url(
    url: str,
    format_type: str = "screenshot",
    full_page: bool = True,
    color_scheme: str = "light",
    delay: int = 0,
    width: int = 1920,
    height: int = 1080
) -> str:
    """
    Navigates to a URL and captures a screenshot or PDF.
    Returns the absolute path to the captured temp file.
    """
    temp_id = f"captured_{generate_short_id()}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": width, "height": height},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Hide Playwright automation signature from Akamai/Cloudflare CDN blocks
        await page.add_init_script("delete navigator.__proto__.webdriver;")
        
        # Emulate dark/light mode
        if color_scheme in ["light", "dark"]:
            await page.emulate_media(color_scheme=color_scheme)
            
        # Navigate to target page with 20s timeout and wait for load event
        await page.goto(url, wait_until="load", timeout=20000)
        
        # Optional delay for lazy loaded assets or animations
        if delay > 0:
            await asyncio.sleep(delay)
            
        if format_type == "pdf":
            file_path = os.path.join(settings.STORAGE_ROOT, "temp", f"{temp_id}.pdf")
            await page.pdf(path=file_path, format="A4", print_background=True)
        else:
            file_path = os.path.join(settings.STORAGE_ROOT, "temp", f"{temp_id}.png")
            await page.screenshot(path=file_path, full_page=full_page)
            
        await browser.close()
        
    return file_path
