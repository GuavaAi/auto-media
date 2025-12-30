"""
DataSourceContent 构造器工厂
统一管理 DataSourceContent 实例的创建，避免重复代码
"""
from datetime import datetime
from typing import Any, Optional
import hashlib

from app.models.datasource_content import DataSourceContent


def compute_url_hash(url: str) -> str:
    """计算 URL 的 MD5 哈希值"""
    return hashlib.md5(str(url).encode("utf-8", "ignore")).hexdigest()


def compute_content_hash(content: str) -> str:
    """计算内容的 MD5 哈希值"""
    return hashlib.md5(content.encode("utf-8", "ignore")).hexdigest()


class ContentFactory:
    """DataSourceContent 构造器工厂类"""

    @staticmethod
    def create_url_content(
        *,
        user_id: Optional[int],
        datasource_id: int,
        url: str,
        title: Optional[str],
        content: str,
        status_code: Optional[int] = None,
        final_url: Optional[str] = None,
        is_discovered: bool = False,
        extractor: Optional[str] = None,
        extractor_meta: Optional[dict] = None,
        content_hash: Optional[str] = None,
        content_hash_clean: Optional[str] = None,
        clean_stats: Optional[dict] = None,
        quality_flags: Optional[dict] = None,
        fetched_at: Optional[datetime] = None,
    ) -> DataSourceContent:
        """
        创建 URL 类型的 DataSourceContent
        用于普通 URL 抓取场景
        """
        url_hash = compute_url_hash(url)
        return DataSourceContent(
            user_id=user_id,
            datasource_id=datasource_id,
            source_type="url",
            title=title or url,
            url=url,
            url_hash=url_hash,
            content=content,
            extra={
                "status_code": status_code,
                "final_url": final_url,
                "is_discovered": is_discovered,
                "extractor": extractor,
                "extractor_meta": extractor_meta,
                "content_hash": content_hash,
                "content_hash_clean": content_hash_clean,
                "clean_stats": clean_stats,
                "quality_flags": quality_flags,
            },
            fetched_at=fetched_at or datetime.now(),
        )

    @staticmethod
    def create_firecrawl_search_content(
        *,
        user_id: Optional[int],
        datasource_id: int,
        url: str,
        title: Optional[str],
        content: str,
        query: str,
        status_code: Optional[int] = None,
        final_url: Optional[str] = None,
        firecrawl_source: Optional[str] = None,
        firecrawl_rank: Optional[int] = None,
        firecrawl_description: Optional[str] = None,
        extractor: Optional[str] = None,
        extractor_meta: Optional[dict] = None,
        content_hash: Optional[str] = None,
        content_hash_clean: Optional[str] = None,
        clean_stats: Optional[dict] = None,
        quality_flags: Optional[dict] = None,
        fetched_at: Optional[datetime] = None,
    ) -> DataSourceContent:
        """
        创建 FireCrawl 搜索模式的 DataSourceContent
        """
        url_hash = compute_url_hash(url)
        return DataSourceContent(
            user_id=user_id,
            datasource_id=datasource_id,
            source_type="url",
            title=title or url,
            url=url,
            url_hash=url_hash,
            content=content,
            extra={
                "status_code": status_code,
                "final_url": final_url,
                "firecrawl_mode": "search",
                "firecrawl_query": query,
                "firecrawl_source": firecrawl_source,
                "firecrawl_rank": firecrawl_rank,
                "firecrawl_title": title,
                "firecrawl_description": firecrawl_description,
                "extractor": extractor,
                "extractor_meta": extractor_meta,
                "content_hash": content_hash,
                "content_hash_clean": content_hash_clean,
                "clean_stats": clean_stats,
                "quality_flags": quality_flags,
            },
            fetched_at=fetched_at or datetime.now(),
        )

    @staticmethod
    def create_aliyun_iqs_content(
        *,
        user_id: Optional[int],
        datasource_id: int,
        url: str,
        title: Optional[str],
        content: str,
        query: str,
        engine_type: str,
        time_range: str,
        category: Optional[str] = None,
        location: Optional[str] = None,
        rank: Optional[int] = None,
        snippet: Optional[str] = None,
        published_time: Optional[str] = None,
        rerank_score: Optional[float] = None,
        content_hash: Optional[str] = None,
        content_hash_clean: Optional[str] = None,
        clean_stats: Optional[dict] = None,
        quality_flags: Optional[dict] = None,
        fetched_at: Optional[datetime] = None,
    ) -> DataSourceContent:
        """
        创建阿里统一搜索模式的 DataSourceContent
        """
        url_hash = compute_url_hash(url)
        return DataSourceContent(
            user_id=user_id,
            datasource_id=datasource_id,
            source_type="url",
            title=title or url,
            url=url,
            url_hash=url_hash,
            content=content,
            extra={
                "iqs_mode": "unified_search",
                "iqs_query": query,
                "iqs_engine_type": engine_type,
                "iqs_time_range": time_range,
                "iqs_category": category,
                "iqs_location": location,
                "iqs_rank": rank,
                "iqs_title": title,
                "iqs_snippet": snippet,
                "iqs_published_time": published_time,
                "iqs_rerank_score": rerank_score,
                "content_hash": content_hash,
                "content_hash_clean": content_hash_clean,
                "clean_stats": clean_stats,
                "quality_flags": quality_flags,
            },
            fetched_at=fetched_at or datetime.now(),
        )

    @staticmethod
    def create_api_content(
        *,
        user_id: Optional[int],
        datasource_id: int,
        api_url: str,
        content: str,
        status_code: Optional[int] = None,
        method: str = "GET",
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        body: Optional[Any] = None,
        content_hash_clean: Optional[str] = None,
        clean_stats: Optional[dict] = None,
        quality_flags: Optional[dict] = None,
        fetched_at: Optional[datetime] = None,
    ) -> DataSourceContent:
        """
        创建 API 调用类型的 DataSourceContent
        """
        return DataSourceContent(
            user_id=user_id,
            datasource_id=datasource_id,
            source_type="api",
            title=api_url,
            content=content,
            extra={
                "status_code": status_code,
                "method": method,
                "headers": headers,
                "params": params,
                "body": body,
                "content_hash_clean": content_hash_clean,
                "clean_stats": clean_stats,
                "quality_flags": quality_flags,
            },
            fetched_at=fetched_at or datetime.now(),
        )

    @staticmethod
    def create_document_content(
        *,
        user_id: Optional[int],
        datasource_id: int,
        doc_url: str,
        content: str,
        status_code: Optional[int] = None,
        content_type: Optional[str] = None,
        headers: Optional[dict] = None,
        content_hash_clean: Optional[str] = None,
        clean_stats: Optional[dict] = None,
        quality_flags: Optional[dict] = None,
        fetched_at: Optional[datetime] = None,
    ) -> DataSourceContent:
        """
        创建文档类型的 DataSourceContent
        """
        return DataSourceContent(
            user_id=user_id,
            datasource_id=datasource_id,
            source_type="document",
            title=doc_url,
            content=content,
            extra={
                "status_code": status_code,
                "content_type": content_type,
                "headers": headers,
                "content_hash_clean": content_hash_clean,
                "clean_stats": clean_stats,
                "quality_flags": quality_flags,
            },
            fetched_at=fetched_at or datetime.now(),
        )

    @staticmethod
    def create_n8n_content(
        *,
        user_id: Optional[int],
        datasource_id: int,
        webhook: str,
        content: str,
        status_code: Optional[int] = None,
        content_hash_clean: Optional[str] = None,
        clean_stats: Optional[dict] = None,
        quality_flags: Optional[dict] = None,
        fetched_at: Optional[datetime] = None,
    ) -> DataSourceContent:
        """
        创建 n8n webhook 类型的 DataSourceContent
        """
        return DataSourceContent(
            user_id=user_id,
            datasource_id=datasource_id,
            source_type="n8n",
            title=webhook,
            content=content,
            extra={
                "status_code": status_code,
                "webhook": webhook,
                "content_hash_clean": content_hash_clean,
                "clean_stats": clean_stats,
                "quality_flags": quality_flags,
            },
            fetched_at=fetched_at or datetime.now(),
        )
