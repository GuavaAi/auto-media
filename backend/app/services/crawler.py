from __future__ import annotations

"""
采集层抓取器抽象与实现，支持 Requests / Playwright（可扩展）。
"""

import os
import time
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from requests import RequestException
from bs4 import BeautifulSoup


@dataclass
class CrawlResult:
    url: str
    html: str
    status_code: Optional[int] = None
    extra: Optional[Dict] = None


class BaseCrawler(ABC):
    """抓取器基类，可扩展不同实现。"""

    @abstractmethod
    def fetch(self, url: str, headers: Optional[Dict] = None, timeout: int = 15) -> CrawlResult:
        """抓取页面并返回 HTML。"""


class RequestsCrawler(BaseCrawler):
    """基于 requests 的简单抓取器，适合静态页面。"""

    def fetch(self, url: str, headers: Optional[Dict] = None, timeout: int = 15) -> CrawlResult:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return CrawlResult(
            url=url,
            html=resp.text,
            status_code=resp.status_code,
            extra={"final_url": resp.url},
        )


class PlaywrightCrawler(BaseCrawler):
    """基于 Playwright 的抓取器，适合需要 JS 渲染的页面。"""

    def fetch(self, url: str, headers: Optional[Dict] = None, timeout: int = 20) -> CrawlResult:
        try:
            from playwright.sync_api import sync_playwright
            from playwright._impl._errors import TimeoutError as PlaywrightTimeoutError
        except Exception as exc:  # pragma: no cover - 依赖缺失时抛出
            raise ImportError("缺少 Playwright 依赖，请安装 playwright 并执行 playwright install") from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(extra_http_headers=headers or {})
            page = context.new_page()
            try:
                try:
                    response = page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                except PlaywrightTimeoutError:
                    # networkidle 在部分站点会长期等不到，降级到 domcontentloaded 再试一次
                    response = page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                # 可视场景等待一小段时间保证异步渲染
                page.wait_for_timeout(500)
                html = page.content()
                status_code = response.status if response else None
                return CrawlResult(url=url, html=html, status_code=status_code, extra={"final_url": page.url})
            except PlaywrightTimeoutError as exc:
                raise RequestException(f"Playwright 抓取超时：{url}") from exc
            finally:
                try:
                    context.close()
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass


class Crawl4aiCrawler(BaseCrawler):
    """基于 crawl4ai 的抓取器，支持本地库或 HTTP(Docker) 两种模式。"""

    def __init__(
        self,
        *,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        self.api_base = api_base.rstrip("/") if api_base else None
        self.api_key = api_key
        self.options = options or {}
        self._session = requests.Session()
        self._local_import_ok = None  # 避免重复导入失败

    def _fetch_via_http(self, url: str, headers: Optional[Dict], timeout: int) -> CrawlResult:
        """调用 crawl4ai Docker API /crawl。"""
        endpoint = f"{self.api_base}/crawl"
        payload: Dict[str, Any] = {"urls": [url], "priority": 10}
        if self.api_key:
            payload["api_token"] = self.api_key
        # 透传可能的运行配置（仅在服务端支持时生效）
        run_cfg: Dict[str, Any] = {}
        if self.options.get("browser"):
            run_cfg["browser"] = self.options["browser"]
        if self.options.get("wait_ms"):
            run_cfg["wait_ms"] = self.options["wait_ms"]
        if self.options.get("js_code"):
            run_cfg["js_code"] = self.options["js_code"]
        if self.options.get("stealth") is not None:
            run_cfg["stealth"] = self.options["stealth"]
        if run_cfg:
            payload["run_config"] = run_cfg

        req_headers = headers.copy() if headers else {}
        try:
            resp = self._session.post(endpoint, json=payload, headers=req_headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise RequestException(f"crawl4ai API 调用失败: {exc}") from exc

        def _looks_like_html(text: Any) -> bool:
            if not isinstance(text, str):
                return False
            t = text.lstrip().lower()
            return t.startswith("<!doctype") or t.startswith("<html") or "<body" in t or "<a" in t

        # 即时返回模式：results 直接存在
        if isinstance(data, dict) and data.get("results"):
            results = data.get("results") or []
            first = results[0] if results else {}
            raw_html = first.get("html")
            markdown = first.get("markdown")
            content = first.get("content")
            html = raw_html or (content if _looks_like_html(content) else None) or markdown or content
            if not html:
                raise RequestException("crawl4ai API 返回为空")
            return CrawlResult(
                url=url,
                html=str(html),
                status_code=200,
                extra={
                    "final_url": first.get("url") or url,
                    "task_id": data.get("task_id"),
                    "crawl4ai_markdown": markdown,
                },
            )

        # 异步任务模式：轮询 task/{id}
        task_id = data.get("task_id")
        if not task_id:
            raise RequestException(f"crawl4ai API 返回格式异常: {data}")
        task_endpoint = f"{self.api_base}/task/{task_id}"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                res = self._session.get(task_endpoint, timeout=5)
                res.raise_for_status()
                jd = res.json()
                if jd.get("status") in ("finished", "success", "done"):
                    results = jd.get("results") or []
                    first = results[0] if results else {}
                    raw_html = first.get("html")
                    markdown = first.get("markdown")
                    content = first.get("content")
                    html = raw_html or (content if _looks_like_html(content) else None) or markdown or content
                    if not html:
                        raise RequestException("crawl4ai 任务结果为空")
                    return CrawlResult(
                        url=url,
                        html=str(html),
                        status_code=200,
                        extra={
                            "final_url": first.get("url") or url,
                            "task_id": task_id,
                            "crawl4ai_markdown": markdown,
                        },
                    )
            except Exception:
                pass
            time.sleep(1)
        raise RequestException(f"crawl4ai 任务超时: {task_id}")

    def _fetch_via_local(self, url: str, headers: Optional[Dict], timeout: int) -> CrawlResult:
        """本地库模式，使用 AsyncWebCrawler/Async 运行，返回 markdown/html。"""
        try:
            from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig  # type: ignore
        except Exception as exc:  # pragma: no cover - 依赖缺失时抛出
            raise ImportError("缺少 crawl4ai 依赖，请安装 crawl4ai") from exc

        import asyncio

        async def _run() -> Any:
            # crawl4ai 的配置项在不同版本会变化，为避免因未知字段导致崩溃，这里只使用最稳定的参数。
            # 如需更丰富的 stealth/proxy/browser 等能力，建议走 Docker API 模式（crawl4ai_api_base）。
            browser_config = BrowserConfig(headless=True)  # type: ignore

            run_cfg_kwargs: Dict[str, Any] = {}
            # crawl4ai 不同版本的 CrawlerRunConfig 参数可能变化，这里通过签名探测来安全注入。
            # - js_code: 可选执行 JS
            # - prompt: 可选提示语，用于指导 crawl4ai 做抽取/整理（若版本不支持将忽略）
            try:
                sig = inspect.signature(CrawlerRunConfig)
                accepted = set(sig.parameters.keys())
            except Exception:
                accepted = set()

            if "js_code" in accepted and self.options.get("js_code"):
                run_cfg_kwargs["js_code"] = self.options["js_code"]
            prompt = self.options.get("prompt")
            if "prompt" in accepted and isinstance(prompt, str) and prompt.strip():
                run_cfg_kwargs["prompt"] = prompt.strip()

            run_config = CrawlerRunConfig(**run_cfg_kwargs)  # type: ignore

            async with AsyncWebCrawler(config=browser_config) as crawler:  # type: ignore
                return await crawler.arun(url=url, config=run_config)  # type: ignore

        result = asyncio.run(_run())

        # 过滤/子页面发现依赖 HTML（css_selector、<a href>），这里优先返回原始 HTML。
        raw_html = getattr(result, "html", None) or getattr(result, "raw_html", None)
        markdown_obj = getattr(result, "markdown", None)
        markdown = markdown_obj.raw_markdown if hasattr(markdown_obj, "raw_markdown") else markdown_obj
        content = getattr(result, "content", None)

        html = raw_html or (content if isinstance(content, str) and "<" in content else None) or markdown or content
        if not html:
            raise RequestException(f"crawl4ai 抓取结果为空: {url}")
        return CrawlResult(
            url=url,
            html=str(html),
            status_code=200,
            extra={"final_url": url, "crawl4ai_markdown": markdown},
        )

    def fetch(self, url: str, headers: Optional[Dict] = None, timeout: int = 30) -> CrawlResult:
        if self.api_base:
            return self._fetch_via_http(url, headers, timeout)
        return self._fetch_via_local(url, headers, timeout)


class FirecrawlCrawler(BaseCrawler):
    """调用 FireCrawl 云端 API 的抓取器，适合反爬/重度渲染页面。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        self.api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        base = (base_url or os.getenv("FIRECRAWL_API_BASE") or "https://api.firecrawl.dev/v2").rstrip("/")
        # 兼容用户可能传入 v1 base：自动提升到 v2
        if base.endswith("/v1"):
            base = base[: -len("/v1")] + "/v2"
        if not base.endswith("/v2") and not base.endswith("/v2/"):
            # 允许用户直接传 https://api.firecrawl.dev
            if base.endswith("api.firecrawl.dev"):
                base = base + "/v2"
        self.base_url = base.rstrip("/")
        self.options = options or {}
        if not self.api_key:
            raise ValueError("FireCrawl API Key 未配置，请设置环境变量 FIRECRAWL_API_KEY")
        self._session = requests.Session()

    def fetch(self, url: str, headers: Optional[Dict] = None, timeout: int = 120) -> CrawlResult:
        endpoint = f"{self.base_url}/scrape"

        # 兼容配置字段：snake_case / camelCase
        formats = self.options.get("formats") or self.options.get("scrape_formats") or ["html"]
        if not isinstance(formats, list) or not formats:
            formats = ["html"]

        payload: Dict[str, Any] = {
            "url": url,
            "formats": formats,
        }

        # 以下字段来自 Firecrawl v2 /scrape
        only_main = self.options.get("onlyMainContent")
        if only_main is None:
            only_main = self.options.get("only_main_content")
        if isinstance(only_main, bool):
            payload["onlyMainContent"] = only_main

        max_age = self.options.get("maxAge")
        if max_age is None:
            max_age = self.options.get("max_age")
        try:
            max_age_int = int(max_age) if max_age is not None else None
        except Exception:
            max_age_int = None
        if max_age_int is not None and max_age_int >= 0:
            payload["maxAge"] = max_age_int

        wait_for = self.options.get("waitFor")
        if wait_for is None:
            wait_for = self.options.get("wait_for")
        try:
            wait_for_int = int(wait_for) if wait_for is not None else None
        except Exception:
            wait_for_int = None
        if wait_for_int is not None and wait_for_int >= 0:
            payload["waitFor"] = wait_for_int

        # Firecrawl 的 headers 字段用于向目标站点透传；这里优先使用 options.headers，其次使用调用方 headers
        fc_headers = self.options.get("headers") if isinstance(self.options.get("headers"), dict) else None
        if fc_headers:
            payload["headers"] = fc_headers
        elif headers:
            payload["headers"] = headers

        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if headers:
            # 注意：这里的 headers 是请求 Firecrawl API 的 headers（例如 trace），不是目标站点 headers
            # 目标站点 headers 应通过 payload["headers"] 传递。
            pass

        resp = self._session.post(endpoint, headers=req_headers, json=payload, timeout=timeout)
        resp.raise_for_status()
        html = resp.text
        meta: Dict[str, Any] | None = None
        try:
            data = resp.json()
            html = (
                (data.get("data", {}) if isinstance(data, dict) else {}).get("html")
                or (data.get("data", {}) if isinstance(data, dict) else {}).get("rawHtml")
                or (data.get("data", {}) if isinstance(data, dict) else {}).get("markdown")
                or (data.get("data", {}) if isinstance(data, dict) else {}).get("content")
                or html
            )
            meta = (data.get("data", {}) if isinstance(data, dict) else {}).get("metadata")
            meta = meta if isinstance(meta, dict) else None
        except Exception:
            pass
        return CrawlResult(
            url=url,
            html=str(html),
            status_code=resp.status_code,
            extra={
                "final_url": (meta.get("sourceURL") if isinstance(meta, dict) else None) or url,
                "firecrawl_metadata": meta,
            },
        )


def get_crawler(use_playwright: bool = False) -> BaseCrawler:
    """兼容旧签名：默认返回 requests/playwright 抓取器。"""
    if use_playwright:
        return PlaywrightCrawler()
    return RequestsCrawler()


def get_crawler_by_engine(
    engine: Optional[str],
    use_playwright: bool = False,
    firecrawl_api_key: Optional[str] = None,
    firecrawl_api_base: Optional[str] = None,
    firecrawl_options: Optional[Dict[str, Any]] = None,
    crawl4ai_api_base: Optional[str] = None,
    crawl4ai_api_key: Optional[str] = None,
    crawl4ai_options: Optional[Dict[str, Any]] = None,
) -> BaseCrawler:
    """
    根据配置选择抓取器实现：
    - requests：默认静态抓取
    - playwright：JS 渲染
    - crawl4ai：需要安装 crawl4ai
    - firecrawl：需要配置 FIRECRAWL_API_KEY
    """
    eng = (engine or "").strip().lower()
    # 中文说明：当未指定引擎但 use_playwright=True 时，优先使用 Playwright
    if not eng:
        if use_playwright:
            return PlaywrightCrawler()
        eng = "crawl4ai"
    if eng == "requests":
        return RequestsCrawler()
    if eng == "playwright":
        return PlaywrightCrawler()
    if eng == "crawl4ai":
        return Crawl4aiCrawler(
            api_base=crawl4ai_api_base,
            api_key=crawl4ai_api_key,
            options=crawl4ai_options,
        )
    if eng == "firecrawl":
        return FirecrawlCrawler(
            api_key=firecrawl_api_key,
            base_url=firecrawl_api_base,
            options=firecrawl_options,
        )
    # 未知配置时回退到默认抓取器
    return get_crawler(use_playwright=use_playwright)


def apply_parser(html: str, parser_cfg: Optional[Dict]) -> str:
    """
    根据配置过滤/抽取正文：
    - css_selector：提取特定块
    - include_keywords / exclude_keywords：关键词包含/排除
    返回过滤后的文本，若为空字符串表示过滤掉。
    """
    if not parser_cfg or not isinstance(parser_cfg, dict):
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return html
    parsed_text = html
    try:
        soup = BeautifulSoup(html, "html.parser")
        css_selector = parser_cfg.get("css_selector")
        looks_like_html = "<" in (html or "") and ">" in (html or "")
        if css_selector and looks_like_html:
            selected = soup.select(css_selector)
            if selected:
                parsed_text = "\n".join([s.get_text(separator="\n", strip=True) for s in selected])
            else:
                return ""
        else:
            parsed_text = soup.get_text(separator="\n", strip=True)
        include_kw = parser_cfg.get("include_keywords") or []
        exclude_kw = parser_cfg.get("exclude_keywords") or []
        text_lower = parsed_text.lower()
        if include_kw and isinstance(include_kw, list):
            if not any(str(k).lower() in text_lower for k in include_kw if k):
                return ""
        if exclude_kw and isinstance(exclude_kw, list):
            if any(str(k).lower() in text_lower for k in exclude_kw if k):
                return ""
    except Exception:
        return html
    return parsed_text


def discover_links(
    html: str,
    base_url: str,
    budget: int,
    seen_set: set[str],
    parser_cfg: Optional[Dict] = None,
) -> List[str]:
    """
    从 HTML 中抽取同域链接，受 budget 限制。
    仅在 parser_cfg.css_selector 指定的区域内查找链接，过滤干扰项。
    """
    import logging
    logger = logging.getLogger(__name__)

    if not budget:
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []

    # 根据 css_selector 限定搜索范围，过滤页面其他区域的干扰链接
    search_roots = [soup]
    css_selector = parser_cfg.get("css_selector") if isinstance(parser_cfg, dict) else None
    if css_selector:
        selected = soup.select(css_selector)
        if selected:
            search_roots = selected
            logger.debug(f"[discover_links] css_selector='{css_selector}' 匹配到 {len(selected)} 个元素")
        else:
            # 选择器未匹配到任何元素，返回空列表避免抓取干扰链接
            logger.warning(f"[discover_links] css_selector='{css_selector}' 未匹配到任何元素，跳过链接发现")
            return []

    links: List[str] = []
    base_host = urlparse(base_url).netloc
    for root in search_roots:
        for a in root.find_all("a", href=True):
            if len(links) >= budget:
                break
            href = a.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue
            full = urljoin(base_url, href)
            if not full.startswith("http"):
                continue
            if urlparse(full).netloc != base_host:
                continue
            if full in seen_set:
                continue
            links.append(full)
        if len(links) >= budget:
            break

    logger.debug(f"[discover_links] 发现 {len(links)} 个链接: {links[:5]}...")
    return links
