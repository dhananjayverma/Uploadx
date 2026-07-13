import os
from playwright.async_api import async_playwright
from config import settings
from services.storage import generate_short_id

async def capture_url(url: str, format_type: str = "screenshot") -> str:
    """
    Navigates to a URL and captures a screenshot or PDF.
    Returns the absolute path to the captured temp file.
    """
    temp_id = f"captured_{generate_short_id()}"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to target page
        await page.goto(url, wait_until="networkidle")
        
        if format_type == "pdf":
            file_path = os.path.join(settings.STORAGE_ROOT, "temp", f"{temp_id}.pdf")
            await page.pdf(path=file_path, format="A4", print_background=True)
        else:
            file_path = os.path.join(settings.STORAGE_ROOT, "temp", f"{temp_id}.png")
            await page.screenshot(path=file_path, full_page=True)
            
        await browser.close()
        
    return file_path
