from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.models.article import Article
from app.models.publish_account import PublishAccount


@dataclass
class PublishResult:
    ok: bool
    provider: str
    action: str
    raw: Dict[str, Any]
    remote_id: Optional[str] = None


class PublishProvider:
    """发布平台 Provider 抽象。

    中文说明：
    - 后续新增平台时实现相同接口即可
    - action 用于区分不同发布动作（draft_create/publish/...) 
    """

    provider: str

    def create_draft(
        self,
        account: PublishAccount,
        article: Article,
        *,
        thumb_image_url: str,
        author: str | None = None,
        digest: str | None = None,
        content_source_url: str | None = None,
    ) -> PublishResult:
        raise NotImplementedError
