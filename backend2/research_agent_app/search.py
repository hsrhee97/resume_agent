from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class WebSearchClient:
    def __init__(
        self,
        provider: str = "tavily",
        tavily_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None,
        timeout: int = 20,
    ) -> None:
        self.provider = provider.lower().strip()
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.serper_api_key = serper_api_key or os.getenv("SERPER_API_KEY")
        self.timeout = timeout

    def search(self, query: str, k: int = 5) -> list[SearchResult]:
        if self.provider == "tavily":
            return self._search_tavily(query, k)
        if self.provider == "serper":
            return self._search_serper(query, k)
        raise ValueError("provider must be one of: tavily, serper")

    def _search_tavily(self, query: str, k: int) -> list[SearchResult]:
        if not self.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is required when provider=tavily")

        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": k,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("results", []):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=(item.get("title") or "").strip(),
                    url=url,
                    snippet=(item.get("content") or "").strip(),
                )
            )
        return results

    def _search_serper(self, query: str, k: int) -> list[SearchResult]:
        if not self.serper_api_key:
            raise RuntimeError("SERPER_API_KEY is required when provider=serper")

        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": self.serper_api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": k},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("organic", []):
            url = (item.get("link") or "").strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=(item.get("title") or "").strip(),
                    url=url,
                    snippet=(item.get("snippet") or "").strip(),
                )
            )
        return results


def fetch_markdown_via_jina(url: str, timeout: int = 20) -> str:
    normalized = url.strip()
    if not normalized:
        return ""
    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"

    response = requests.get(
        f"https://r.jina.ai/{normalized}",
        headers={"User-Agent": "resume-research-agent/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.text
