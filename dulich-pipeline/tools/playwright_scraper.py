"""
Playwright Scraper — Scrapes tourism news and trends from multiple sources.
Uses Playwright MCP for browser automation.
"""

import asyncio
from typing import List, Dict
from playwright.async_api import async_playwright


class TourismScraper:
    def __init__(self):
        self.sources = [
            {
                "url": "https://www.google.com/travel",
                "selectors": {"headlines": "h3", "links": "a[href*='/travel']"},
            },
            # Add more sources as needed
        ]

    async def scrape_source(self, source: Dict) -> List[Dict]:
        results = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(source["url"], wait_until="domcontentloaded", timeout=15000)

            headlines = await page.query_selector_all(source["selectors"]["headlines"])
            for h in headlines[:10]:
                text = await h.inner_text()
                if text.strip():
                    results.append({"headline": text.strip(), "source": source["url"]})

            await browser.close()
        return results

    async def scrape_all(self) -> List[Dict]:
        all_results = []
        for source in self.sources:
            try:
                items = await self.scrape_source(source)
                all_results.extend(items)
            except Exception as e:
                print(f"Scrape error for {source['url']}: {e}")
        return all_results

    def run(self) -> List[Dict]:
        return asyncio.run(self.scrape_all())
