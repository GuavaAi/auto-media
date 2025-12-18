from __future__ import annotations

import os
import requests
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.api_key_pool import pick_api_key


class FirecrawlService:
    """Firecrawl API 服务封装，提供实时搜索与内容抓取能力。"""

    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None):
        self.settings = get_settings()
        self._env_api_key = api_key or os.getenv("FIRECRAWL_API_KEY")
        self.api_base = (
            api_base or os.getenv("FIRECRAWL_API_BASE") or "https://api.firecrawl.dev/v2"
        ).rstrip("/")
        
        # 兼容 v2 路径
        if self.api_base.endswith("/v1"):
            self.api_base = self.api_base[:-3] + "/v2"
        if not self.api_base.endswith("/v2") and not self.api_base.endswith("/v2/"):
            if "api.firecrawl.dev" in self.api_base and "/v" not in self.api_base:
                self.api_base = self.api_base + "/v2"

    def _get_api_key(self, db: Optional[Session] = None) -> str:
        """获取可用 API Key：优先使用环境变量/初始化参数，其次尝试从 API Key Pool 获取。"""
        if self._env_api_key:
            return self._env_api_key
        
        if db:
            picked = pick_api_key(db, "firecrawl", mark_used=True)
            if picked and picked.key:
                return picked.key
        
        raise ValueError("FireCrawl API Key 未配置（环境变量或 API Key 池均未找到可用 Key）")

    def _get_headers(self, db: Optional[Session] = None) -> Dict[str, str]:
        api_key = self._get_api_key(db)
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def search(
        self, query: str, limit: int = 5, sources: Optional[List[str]] = None, db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        执行实时搜索，返回标准化结果列表。
        
        Args:
            query: 搜索关键词
            limit: 返回条数
            sources: 来源过滤，默认 ["web"]
            db: 数据库会话（用于从 API Key Pool 获取 Key）
            
        Returns:
            List[Dict]: 包含 url, title, description, markdown/content 等字段的字典列表
        """
        endpoint = f"{self.api_base}/search"
        payload = {
            "query": query,
            "limit": limit,
            "sources": sources or ["web"],
            "scrapeOptions": {
                "formats": ["markdown"],  # 优先获取 markdown
            },
        }

        try:
            resp = requests.post(
                endpoint, json=payload, headers=self._get_headers(db), timeout=60
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            # 记录日志或静默失败？视业务需求。这里抛出异常以便上层感知。
            raise RuntimeError(f"Firecrawl 搜索失败: {str(e)}") from e

        if not data.get("success"):
            raise RuntimeError(f"Firecrawl 搜索返回异常: {data}")

        # 标准化输出
        results = []
        raw_data = data.get("data", {})
        # v2 search response structure: { data: { web: [...], news: [...] } }
        # 我们这里主要合并所有 sources 的结果
        
        items = []
        for src in (sources or ["web"]):
            items.extend(raw_data.get(src, []))

        for it in items:
            # 尽可能提取有效信息
            markdown = it.get("markdown") or it.get("content") or ""
            meta = it.get("metadata") or {}
            
            results.append({
                "url": it.get("url"),
                "title": it.get("title") or meta.get("title"),
                "description": it.get("description") or meta.get("description"),
                "content": markdown,  # 这里的 markdown 通常是经过 Firecrawl 处理的正文
                "source": "firecrawl_search",
                "meta": meta,
            })
            
        return results

# 全局单例（可直接 import 使用）
firecrawl_service = FirecrawlService()

