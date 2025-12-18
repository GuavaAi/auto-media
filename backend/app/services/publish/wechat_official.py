from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict

import requests

from app.models.article import Article
from app.models.publish_account import PublishAccount
from app.services.publish.errors import PublishError
from app.services.publish.provider_base import PublishProvider, PublishResult
from app.services.publish.token_cache import TokenCache, build_token_cache


WECHAT_DRAFT_TITLE_MAX_BYTES = 64


logger = logging.getLogger("uvicorn.error")


def _truncate_utf8_bytes(text: str, max_bytes: int) -> str:
    raw = (text or "").encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    cut = raw[:max_bytes]
    while cut:
        try:
            return cut.decode("utf-8")
        except UnicodeDecodeError:
            cut = cut[:-1]
    return ""


def _unescape_unicode_sequences(text: str) -> str:
    """将字符串中的 \\uXXXX / \\UXXXXXXXX 转义序列解码为真实 Unicode。

    中文说明：
    - 某些内容可能来自 JSON 序列化结果（例如包含字面量 \\u5173\\u6ce8），若直接传给微信会显示为“乱码”。
    - 这里仅在检测到转义模式时解码，避免误伤正常内容。
    """

    s = text or ""
    if "\\u" not in s and "\\U" not in s:
        return s

    # 中文说明：兼容被二次转义的场景（字符串里出现 "\\\\u5173" 这种形式）
    # 这里仅对 \u/\U 模式做归一化，避免影响其它合法反斜杠内容。
    while "\\\\u" in s or "\\\\U" in s:
        s = s.replace("\\\\u", "\\u").replace("\\\\U", "\\U")

    def _repl_u(m: re.Match) -> str:
        return chr(int(m.group(1), 16))

    def _repl_U(m: re.Match) -> str:
        return chr(int(m.group(1), 16))

    s = re.sub(r"\\u([0-9a-fA-F]{4})", _repl_u, s)
    s = re.sub(r"\\U([0-9a-fA-F]{8})", _repl_U, s)
    return s


class WechatOfficialProvider(PublishProvider):
    provider = "wechat_official"

    def __init__(self, token_cache: TokenCache | None = None) -> None:
        self._token_cache = token_cache or build_token_cache()

    def _get_app_credentials(self, account: PublishAccount) -> tuple[str, str]:
        cfg = account.config if isinstance(account.config, dict) else {}
        appid = str(cfg.get("appid") or "").strip()
        secret = str(cfg.get("secret") or "").strip()
        if not (appid and secret):
            raise PublishError("bad_config", "公众号账号未配置 appid/secret")
        return appid, secret

    def _get_access_token(self, account: PublishAccount) -> str:
        appid, secret = self._get_app_credentials(account)
        cache_key = f"wechat_official:access_token:{appid}"
        cached = self._token_cache.get(cache_key)
        if cached:
            return cached

        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": appid,
            "secret": secret,
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            jd = resp.json()
        except Exception as exc:
            raise PublishError("token_request_failed", f"获取 access_token 失败：{exc}") from exc

        if not isinstance(jd, dict) or not jd.get("access_token"):
            raise PublishError("token_bad_response", f"获取 access_token 返回异常：{jd}")

        token = str(jd.get("access_token"))
        expires_in = int(jd.get("expires_in") or 7200)
        # 中文说明：留 60 秒安全边界，避免临近过期引发失败。
        ttl = max(60, expires_in - 60)
        self._token_cache.set(cache_key, token, ttl)
        return token

    def _download_image(self, url: str) -> tuple[bytes, str]:
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            data = r.content
        except Exception as exc:
            raise PublishError("thumb_download_failed", f"封面图下载失败：{exc}") from exc

        if not data:
            raise PublishError("thumb_download_failed", "封面图下载为空")

        # 尽量从 URL 推断扩展名
        filename = "cover.jpg"
        lowered = url.lower()
        if ".png" in lowered:
            filename = "cover.png"
        elif ".jpeg" in lowered or ".jpg" in lowered:
            filename = "cover.jpg"
        elif ".gif" in lowered:
            filename = "cover.gif"
        return data, filename

    def _upload_thumb(self, access_token: str, image_url: str) -> str:
        data, filename = self._download_image(image_url)

        # 公众号封面需要用素材接口拿到 media_id
        url = "https://api.weixin.qq.com/cgi-bin/material/add_material"
        params = {"access_token": access_token, "type": "image"}
        files = {"media": (filename, data)}
        try:
            resp = requests.post(url, params=params, files=files, timeout=120)
            resp.raise_for_status()
            jd = resp.json()
        except Exception as exc:
            raise PublishError("thumb_upload_failed", f"封面上传失败：{exc}") from exc

        if not isinstance(jd, dict) or not jd.get("media_id"):
            raise PublishError("thumb_upload_bad_response", f"封面上传返回异常：{jd}")

        return str(jd.get("media_id"))

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
        access_token = self._get_access_token(account)
        thumb_media_id = self._upload_thumb(access_token, thumb_image_url)

        # 中文说明：draft/add 要求 content 为 HTML（微信编辑器兼容 HTML）。
        raw_title_0 = article.title or ""
        raw_title_1 = _unescape_unicode_sequences(raw_title_0)
        title_normalized = raw_title_1.replace("\n", " ").replace("\r", " ").strip() or f"article-{article.id}"
        title = _truncate_utf8_bytes(title_normalized, WECHAT_DRAFT_TITLE_MAX_BYTES).strip() or f"article-{article.id}"

        logger.info(
            "wechat_draft_title_debug article_id=%s raw=%r raw_len=%s raw_bytes=%s decoded=%r decoded_len=%s decoded_bytes=%s normalized=%r normalized_len=%s normalized_bytes=%s final=%r final_len=%s final_bytes=%s max_bytes=%s",
            getattr(article, "id", None),
            raw_title_0,
            len(raw_title_0),
            len(raw_title_0.encode("utf-8")),
            raw_title_1,
            len(raw_title_1),
            len(raw_title_1.encode("utf-8")),
            title_normalized,
            len(title_normalized),
            len(title_normalized.encode("utf-8")),
            title,
            len(title),
            len(title.encode("utf-8")),
            WECHAT_DRAFT_TITLE_MAX_BYTES,
        )
        content_html = _unescape_unicode_sequences(article.content_html or "").strip()
        if not content_html:
            raise PublishError("empty_content", "文章 HTML 为空，无法发布到草稿箱")

        author = _unescape_unicode_sequences((author or "").strip()) or None
        digest = _unescape_unicode_sequences((digest or "").strip()) or None
        content_source_url = _unescape_unicode_sequences((content_source_url or "").strip()) or None

        payload: Dict[str, Any] = {
            "articles": [
                {
                    "title": title,
                    "author": author or "",
                    "digest": digest or "",
                    "content": content_html,
                    "content_source_url": content_source_url or "",
                    "thumb_media_id": thumb_media_id,
                    "need_open_comment": 0,
                    "only_fans_can_comment": 0,
                }
            ]
        }

        url = "https://api.weixin.qq.com/cgi-bin/draft/add"
        params = {"access_token": access_token}
        def _post_once(p: dict):
            # 中文说明：requests 的 json= 默认 ensure_ascii=True，会把中文转成 \uXXXX。
            # 微信侧可能按字节/字符做校验时把 \uXXXX 当作实际内容，导致标题超限或显示乱码。
            body = json.dumps(p, ensure_ascii=False).encode("utf-8")
            resp = requests.post(
                url,
                params=params,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()

        try:
            jd = _post_once(payload)
        except Exception as exc:
            raise PublishError("draft_create_failed", f"创建草稿失败：{exc}") from exc

        if not isinstance(jd, dict):
            raise PublishError("draft_bad_response", f"创建草稿返回异常：{jd}")

        # 微信 errcode=0 表示成功
        errcode = int(jd.get("errcode") or 0)
        if errcode != 0:
            errmsg = str(jd.get("errmsg") or "")
            final_title = payload.get("articles", [{}])[0].get("title")
            title_bytes = len(str(final_title or "").encode("utf-8"))
            if "title size out of limit" in errmsg:
                errmsg = f"{errmsg} (title_bytes={title_bytes}, max={WECHAT_DRAFT_TITLE_MAX_BYTES})"
            raise PublishError(
                "draft_err",
                f"创建草稿失败：{errmsg}",
                detail={
                    "wechat": jd,
                    "debug": {
                        "title": final_title,
                        "title_bytes": title_bytes,
                        "title_max_bytes": WECHAT_DRAFT_TITLE_MAX_BYTES,
                    },
                },
            )

        media_id = jd.get("media_id")
        return PublishResult(
            ok=True,
            provider=self.provider,
            action="draft_create",
            raw=jd,
            remote_id=str(media_id) if media_id else None,
        )


provider_singleton = WechatOfficialProvider()
