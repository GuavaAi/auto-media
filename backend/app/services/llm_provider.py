from abc import ABC, abstractmethod
import os
import time
from typing import Any, Dict, Optional

import requests
from requests import RequestException, Timeout
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.api_key_pool import pick_api_key


class LLMProvider(ABC):
    """多模型供应商抽象类"""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """根据 prompt 生成文本"""


class OpenAIProvider(LLMProvider):
    def __init__(self, *, db: Session | None = None):
        self._db = db

    def generate(self, prompt: str, **kwargs: Any) -> str:
        settings = get_settings()

        # 中文说明：测试环境下默认避免外网依赖。
        # 但如果测试显式注入了 API Key 池并 monkeypatch requests.post，则应走真实调用路径。
        # 如确需在 pytest 中强制验证真实调用，可设置 OPENAI_MOCK_DISABLED=true。
        mock_disabled = (os.getenv("OPENAI_MOCK_DISABLED") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        # 1) 优先从 API Key 池取 key + 额外配置
        api_key = None
        key_from_pool = False
        extra: Dict[str, Any] = {}
        if self._db is not None:
            k = pick_api_key(self._db, "openai", mark_used=True)
            if k:
                api_key = k.key
                key_from_pool = True
                if isinstance(getattr(k, "extra", None), dict):
                    extra = k.extra or {}

        # 2) 兜底：环境变量
        api_key = api_key or settings.MODEL_API_KEY_OPENAI

        if os.getenv("PYTEST_CURRENT_TEST") and (not mock_disabled) and (not key_from_pool):
            return f"[openai mock] {prompt}".strip()

        if not api_key:
            # 中文说明：为了本地体验不强依赖真实 OpenAI Key，提供可控的 mock 兜底。
            if (settings.ENV or "dev") != "prod" and not mock_disabled:
                return f"[openai mock] {prompt}".strip()
            raise ValueError("缺少 OpenAI API Key，请在 API Key 池(openai) 或环境变量 MODEL_API_KEY_OPENAI 配置")

        base_url = str(extra.get("base_url") or settings.MODEL_OPENAI_API_BASE or "").rstrip("/")
        model = str(extra.get("model") or settings.MODEL_OPENAI_MODEL or "").strip()
        if not base_url:
            base_url = "https://api.openai.com/v1"
        if not model:
            # 中文说明：生产建议显式配置模型；非生产提供默认值提升可用性。
            if (settings.ENV or "dev") != "prod":
                model = (os.getenv("OPENAI_DEFAULT_MODEL") or "gpt-4o-mini").strip() or "gpt-4o-mini"
            else:
                raise ValueError("缺少 OpenAI model 配置，请在 API Key 池 extra.model 或环境变量 MODEL_OPENAI_MODEL 配置")

        temperature = kwargs.get("temperature", 0.7) or 0.7
        max_tokens = kwargs.get("max_tokens") or _estimate_tokens(kwargs.get("length"))
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        timeout = int(extra.get("timeout") or settings.MODEL_OPENAI_TIMEOUT or 60)
        verify = bool(extra.get("verify") if "verify" in extra else settings.MODEL_OPENAI_VERIFY)

        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=timeout,
                verify=verify,
            )
        except Timeout as exc:
            raise ValueError("OpenAI 请求超时，请稍后重试或缩短生成字数") from exc
        except RequestException as exc:
            raise ValueError(f"OpenAI 请求异常: {exc}") from exc

        if resp.status_code >= 300:
            raise ValueError(f"OpenAI 请求失败: {resp.status_code} {resp.text}")

        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise ValueError("OpenAI 返回内容为空")
        return content


class MoonshotProvider(LLMProvider):
    """Moonshot(Kimi) OpenAI 兼容接口实现。

    说明：Moonshot 提供 OpenAI compatible 的 /chat/completions。
    本项目为了保持依赖轻量，复用 requests 调用。
    """

    def __init__(self, *, db: Session | None = None):
        self._db = db

    def generate(self, prompt: str, **kwargs: Any) -> str:
        settings = get_settings()

        api_key = None
        extra: Dict[str, Any] = {}
        if self._db is not None:
            k = pick_api_key(self._db, "moonshot", mark_used=True)
            if not k:
                k = pick_api_key(self._db, "kimi", mark_used=True)
            if k:
                api_key = k.key
                if isinstance(getattr(k, "extra", None), dict):
                    extra = k.extra or {}

        api_key = api_key or getattr(settings, "MODEL_API_KEY_MOONSHOT", None)
        if not api_key:
            raise ValueError("缺少 Moonshot(Kimi) API Key，请在 API Key 池(moonshot/kimi) 或环境变量 MODEL_API_KEY_MOONSHOT 配置")

        base_url = str(extra.get("base_url") or extra.get("api_base") or getattr(settings, "MODEL_MOONSHOT_API_BASE", None) or "").rstrip("/")
        if not base_url:
            base_url = "https://api.moonshot.cn/v1"

        model = str(extra.get("model") or getattr(settings, "MODEL_MOONSHOT_MODEL", None) or "").strip()
        if not model:
            model = "kimi-k2-turbo-preview"

        temperature = kwargs.get("temperature", 0.7) or 0.7
        max_tokens = kwargs.get("max_tokens") or _estimate_tokens(kwargs.get("length"))
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        timeout = int(extra.get("timeout") or 60)
        verify = bool(extra.get("verify") if "verify" in extra else True)

        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=timeout,
                verify=verify,
            )
        except Timeout as exc:
            raise ValueError("Moonshot(Kimi) 请求超时，请稍后重试或缩短生成字数") from exc
        except RequestException as exc:
            raise ValueError(f"Moonshot(Kimi) 请求异常: {exc}") from exc

        if resp.status_code >= 300:
            raise ValueError(f"Moonshot(Kimi) 请求失败: {resp.status_code} {resp.text}")

        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise ValueError("Moonshot(Kimi) 返回内容为空")
        return content


class AliProvider(LLMProvider):
    def __init__(self, *, db: Session | None = None):
        self._db = db

    def generate(self, prompt: str, **kwargs: Any) -> str:
        settings = get_settings()

        api_key = None
        extra: Dict[str, Any] = {}
        if self._db is not None:
            # 兼容多种别名，方便前端/配置使用
            k = pick_api_key(self._db, "ali", mark_used=True)
            if not k:
                k = pick_api_key(self._db, "dashscope", mark_used=True)
            if not k:
                k = pick_api_key(self._db, "tongyi", mark_used=True)
            if not k:
                k = pick_api_key(self._db, "qwen", mark_used=True)
            if k:
                api_key = k.key
                if isinstance(getattr(k, "extra", None), dict):
                    extra = k.extra or {}

        api_key = api_key or settings.MODEL_API_KEY_ALI
        if not api_key:
            raise ValueError("缺少通义千问 API Key，请在 API Key 池(ali/dashscope/tongyi/qwen) 或环境变量 MODEL_API_KEY_ALI 配置")

        base_url = str(extra.get("base_url") or extra.get("api_base") or "").rstrip("/")
        if not base_url:
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        model = str(extra.get("model") or "").strip()
        if not model:
            model = "qwen-plus"

        temperature = kwargs.get("temperature", 0.7) or 0.7
        max_tokens = kwargs.get("max_tokens") or _estimate_tokens(kwargs.get("length"))
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        timeout = int(extra.get("timeout") or 60)
        verify = bool(extra.get("verify") if "verify" in extra else True)

        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=timeout,
                verify=verify,
            )
        except Timeout as exc:
            raise ValueError("通义千问请求超时，请稍后重试或缩短生成字数") from exc
        except RequestException as exc:
            raise ValueError(f"通义千问请求异常: {exc}") from exc

        if resp.status_code >= 300:
            raise ValueError(f"通义千问请求失败: {resp.status_code} {resp.text}")

        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise ValueError("通义千问返回内容为空")
        return content


_BAIDU_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _baidu_cache_key(client_id: str, client_secret: str, token_base: str) -> str:
    return f"{token_base}::{client_id}::{client_secret}"


def _baidu_get_access_token(
    *,
    client_id: str,
    client_secret: str,
    token_base: str,
    timeout: int,
    verify: bool,
) -> str:
    """获取百度 OAuth access_token，并做进程内缓存。

    中文说明：
    - 文心/千帆的 access_token 默认有效期较长（通常 30 天），这里用 expires_in 做兜底缓存。
    - 为避免 token 刚过期导致边界失败，这里提前 60 秒过期。
    """

    ck = _baidu_cache_key(client_id, client_secret, token_base)
    cached = _BAIDU_TOKEN_CACHE.get(ck)
    now = time.time()
    if cached and cached[1] > now:
        return cached[0]

    try:
        resp = requests.post(
            f"{token_base.rstrip('/')}/oauth/2.0/token",
            params={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=timeout,
            verify=verify,
        )
    except Timeout as exc:
        raise ValueError("百度 access_token 获取超时") from exc
    except RequestException as exc:
        raise ValueError(f"百度 access_token 获取异常: {exc}") from exc

    if resp.status_code >= 300:
        raise ValueError(f"百度 access_token 获取失败: {resp.status_code} {resp.text}")

    data = resp.json() or {}
    token = (data.get("access_token") or "").strip()
    if not token:
        raise ValueError(f"百度 access_token 响应缺少 access_token: {data}")

    expires_in = int(data.get("expires_in") or 0)

    # 默认兜底：2 小时（避免意外返回 0）
    ttl = expires_in if expires_in > 0 else 7200
    _BAIDU_TOKEN_CACHE[ck] = (token, now + max(60, ttl - 60))
    return token


class BaiduProvider(LLMProvider):
    """百度文心（千帆/Wenxin Workshop）Provider。

    中文说明：
    - 最新推荐：使用千帆 OpenAI-Compatible API（API Key 直连）
      - POST https://qianfan.baidubce.com/v2/chat/completions
      - Header: Authorization: Bearer <API Key>
      - （可选）Header: appid: <appid>
    - 兼容模式：若配置了 client_secret，则走 OAuth client_credentials 获取 access_token，
      再调用 Wenxin Workshop 的 chat 接口：/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model}
    - provider 名称兼容：baidu / wenxin / qianfan
    """

    def __init__(self, *, db: Session | None = None):
        self._db = db

    def generate(self, prompt: str, **kwargs: Any) -> str:
        settings = get_settings()

        api_key = None
        client_id = None
        client_secret = None
        extra: Dict[str, Any] = {}

        if self._db is not None:
            # 兼容多种别名，方便配置与迁移
            k = pick_api_key(self._db, "baidu", mark_used=True)
            if not k:
                k = pick_api_key(self._db, "wenxin", mark_used=True)
            if not k:
                k = pick_api_key(self._db, "qianfan", mark_used=True)
            if k:
                # 中文说明：
                # - APIKey 直连：k.key 为千帆 API Key（bce-v3/...）。
                # - OAuth 兼容：k.key 为 client_id。
                api_key = (k.key or "").strip() or None
                client_id = api_key
                if isinstance(getattr(k, "extra", None), dict):
                    extra = k.extra or {}
                client_secret = (
                    str(extra.get("secret") or extra.get("client_secret") or extra.get("api_secret") or "").strip()
                    or None
                )

        # 兜底：环境变量
        api_key = api_key or (settings.MODEL_API_KEY_BAIDU or None)
        client_id = client_id or api_key
        client_secret = client_secret or (os.getenv("MODEL_API_SECRET_BAIDU") or "").strip() or None

        # 是否强制使用旧的 OAuth 模式（兼容场景）
        force_oauth = (str(extra.get("use_oauth") or os.getenv("MODEL_BAIDU_USE_OAUTH") or "") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        timeout = int(extra.get("timeout") or 60)
        verify = bool(extra.get("verify") if "verify" in extra else True)

        model = str(extra.get("model") or os.getenv("MODEL_BAIDU_MODEL") or "ernie-5.0-thinking-latest").strip()
        temperature = kwargs.get("temperature", 0.7) or 0.7
        max_tokens = int(kwargs.get("max_tokens") or _estimate_tokens(kwargs.get("length")))

        # 1) 最新：API Key 直连（OpenAI-Compatible）
        if api_key and (not force_oauth):
            base_url = str(
                extra.get("base_url")
                or extra.get("api_base")
                or os.getenv("MODEL_BAIDU_API_BASE")
                or "https://qianfan.baidubce.com/v2"
            ).rstrip("/")

            appid = str(extra.get("appid") or os.getenv("MODEL_BAIDU_APPID") or "").strip()

            system_prompt = (
                (kwargs.get("system") or kwargs.get("system_prompt") or extra.get("system") or extra.get("system_prompt") or os.getenv("MODEL_BAIDU_SYSTEM_PROMPT"))
                or ""
            )
            system_prompt = str(system_prompt).strip()

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": float(temperature),
                "max_tokens": int(max_tokens),
            }

            # 常用参数透传（与 OpenAI 风格对齐）
            if "top_p" in kwargs and kwargs.get("top_p") is not None:
                payload["top_p"] = float(kwargs.get("top_p"))
            if "stream" in kwargs and kwargs.get("stream") is not None:
                payload["stream"] = bool(kwargs.get("stream"))
            if "stop" in kwargs and kwargs.get("stop") is not None:
                payload["stop"] = kwargs.get("stop")

            # 中文说明：下面两个字段是千帆平台示例中常用的开关，默认不启用检索与引用。
            if "disable_search" in kwargs:
                payload["disable_search"] = bool(kwargs.get("disable_search"))
            if "enable_citation" in kwargs:
                payload["enable_citation"] = bool(kwargs.get("enable_citation"))

            headers: Dict[str, str] = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            if appid:
                headers["appid"] = appid

            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                    verify=verify,
                )
            except Timeout as exc:
                raise ValueError("百度千帆请求超时，请稍后重试或缩短生成字数") from exc
            except RequestException as exc:
                raise ValueError(f"百度千帆请求异常: {exc}") from exc

            if resp.status_code >= 300:
                raise ValueError(f"百度千帆请求失败: {resp.status_code} {resp.text}")

            data = resp.json() or {}
            content = (
                (data.get("choices") or [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            content = (content or "").strip()
            if not content:
                raise ValueError(f"百度千帆返回内容为空: {data}")
            return content

        # 2) 兼容：OAuth + Workshop chat（仅在显式启用时使用）
        if not api_key:
            raise ValueError(
                "缺少百度千帆 API Key，请在 API Key 池(baidu/wenxin/qianfan) 的 key 或环境变量 MODEL_API_KEY_BAIDU 配置"
            )
        if not client_secret:
            raise ValueError(
                "已启用百度 OAuth 兼容模式，但缺少 client_secret。请在 API Key 池 extra.secret 或环境变量 MODEL_API_SECRET_BAIDU 配置"
            )

        token_base = str(extra.get("token_base") or extra.get("token_api_base") or "https://aip.baidubce.com").rstrip("/")
        api_base = str(extra.get("workshop_base") or extra.get("workshop_api_base") or "https://aip.baidubce.com").rstrip("/")

        access_token = _baidu_get_access_token(
            client_id=client_id,
            client_secret=client_secret,
            token_base=token_base,
            timeout=timeout,
            verify=verify,
        )

        payload2: Dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(temperature),
            "max_output_tokens": int(max_tokens),
            "stream": False,
        }

        url2 = f"{api_base}/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model}"
        try:
            resp2 = requests.post(
                url2,
                params={"access_token": access_token},
                json=payload2,
                timeout=timeout,
                verify=verify,
            )
        except Timeout as exc:
            raise ValueError("百度文心请求超时，请稍后重试或缩短生成字数") from exc
        except RequestException as exc:
            raise ValueError(f"百度文心请求异常: {exc}") from exc

        if resp2.status_code >= 300:
            raise ValueError(f"百度文心请求失败: {resp2.status_code} {resp2.text}")

        data2 = resp2.json() or {}
        if data2.get("error_code"):
            raise ValueError(f"百度文心返回错误: {data2.get('error_code')} {data2.get('error_msg')}")

        content2 = (data2.get("result") or "").strip()
        if not content2:
            raise ValueError(f"百度文心返回内容为空: {data2}")
        return content2


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI（兼容 Chat Completions）"""

    def __init__(self, *, db: Session | None = None):
        self._db = db

    def generate(self, prompt: str, **kwargs: Any) -> str:
        settings = get_settings()

        api_key = None
        extra: Dict[str, Any] = {}
        if self._db is not None:
            k = pick_api_key(self._db, "azure_openai", mark_used=True)
            if not k:
                # 兼容 provider=azure
                k = pick_api_key(self._db, "azure", mark_used=True)
            if k:
                api_key = k.key
                if isinstance(getattr(k, "extra", None), dict):
                    extra = k.extra or {}

        api_key = api_key or settings.MODEL_API_KEY_AZURE_OPENAI
        if not api_key:
            raise ValueError("缺少 Azure OpenAI API Key，请在 API Key 池(azure_openai) 或环境变量 MODEL_API_KEY_AZURE_OPENAI 配置")

        endpoint = str(extra.get("endpoint") or settings.MODEL_AZURE_OPENAI_ENDPOINT or "").rstrip("/")
        deployment = str(extra.get("deployment") or settings.MODEL_AZURE_OPENAI_DEPLOYMENT or "").strip()
        api_version = str(extra.get("api_version") or settings.MODEL_AZURE_OPENAI_API_VERSION or "").strip()
        if not endpoint or not deployment or not api_version:
            raise ValueError(
                "Azure OpenAI 配置不完整，请在 API Key 池 extra 中配置 endpoint/deployment/api_version（或环境变量中配置）"
            )

        temperature = kwargs.get("temperature", 0.7) or 0.7
        max_tokens = kwargs.get("max_tokens") or _estimate_tokens(kwargs.get("length"))
        payload: Dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        timeout = int(extra.get("timeout") or settings.MODEL_AZURE_OPENAI_TIMEOUT or 60)
        verify = bool(extra.get("verify") if "verify" in extra else settings.MODEL_AZURE_OPENAI_VERIFY)

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions"

        try:
            resp = requests.post(
                url,
                params={"api-version": api_version},
                headers={"api-key": api_key},
                json=payload,
                timeout=timeout,
                verify=verify,
            )
        except Timeout as exc:
            raise ValueError("Azure OpenAI 请求超时，请稍后重试或缩短生成字数") from exc
        except RequestException as exc:
            raise ValueError(f"Azure OpenAI 请求异常: {exc}") from exc

        if resp.status_code >= 300:
            raise ValueError(f"Azure OpenAI 请求失败: {resp.status_code} {resp.text}")

        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise ValueError("Azure OpenAI 返回内容为空")
        return content


def _estimate_tokens(length: Optional[int]) -> int:
    """简易估算 token，汉字约 1.5~2 token，这里取 2 以防截断"""
    if not length:
        return 2048
    estimated = length * 2
    return min(max(256, estimated), 4096)


class DeepSeekProvider(LLMProvider):
    """DeepSeek 接入实现"""

    def __init__(self, *, db: Session | None = None):
        self._db = db

    def generate(self, prompt: str, **kwargs: Any) -> str:
        settings = get_settings()

        api_key = None
        extra: Dict[str, Any] = {}
        if self._db is not None:
            k = pick_api_key(self._db, "deepseek", mark_used=True)
            if k:
                api_key = k.key
                if isinstance(getattr(k, "extra", None), dict):
                    extra = k.extra or {}

        api_key = api_key or settings.MODEL_API_KEY_DEEPSEEK
        if not api_key:
            raise ValueError("缺少 DeepSeek API Key，请在 API Key 池(deepseek) 或环境变量 MODEL_API_KEY_DEEPSEEK 配置")

        api_base = str(extra.get("api_base") or settings.MODEL_DEEPSEEK_API_BASE or "").rstrip("/")
        model = str(extra.get("model") or settings.MODEL_DEEPSEEK_MODEL or "").strip()
        timeout = int(extra.get("timeout") or settings.MODEL_DEEPSEEK_TIMEOUT)
        verify = bool(extra.get("verify") if "verify" in extra else settings.MODEL_DEEPSEEK_VERIFY)

        temperature = kwargs.get("temperature", 0.7) or 0.7
        max_tokens = kwargs.get("max_tokens") or _estimate_tokens(kwargs.get("length"))
        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
        }

        try:
            resp = requests.post(
                f"{api_base}/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
                timeout=timeout,
                verify=verify,
            )
        except Timeout as exc:
            raise ValueError("DeepSeek 请求超时，请稍后重试或缩短生成字数") from exc
        except RequestException as exc:
            raise ValueError(f"DeepSeek 请求异常: {exc}") from exc

        if resp.status_code >= 300:
            raise ValueError(f"DeepSeek 请求失败: {resp.status_code} {resp.text}")

        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            raise ValueError("DeepSeek 返回内容为空")
        return content


def get_provider(provider: str | None = None, *, db: Session | None = None) -> LLMProvider:
    """根据名称获取对应的模型供应商"""
    settings = get_settings()
    name = (provider or settings.DEFAULT_MODEL_PROVIDER).lower()
    if name == "openai":
        return OpenAIProvider(db=db)
    if name in {"azure_openai", "azure"}:
        return AzureOpenAIProvider(db=db)
    if name in {"ali", "dashscope", "tongyi"}:
        return AliProvider(db=db)
    if name in {"moonshot", "kimi"}:
        return MoonshotProvider(db=db)
    if name in {"baidu", "wenxin", "qianfan"}:
        return BaiduProvider(db=db)
    if name in {"deepseek"}:
        return DeepSeekProvider(db=db)
    raise ValueError(f"不支持的模型供应商: {name}")


def get_provider_model_name(provider: str | None = None) -> str | None:
    """获取当前 provider 对应的模型名称（尽量用于落库展示）。"""
    settings = get_settings()
    name = (provider or settings.DEFAULT_MODEL_PROVIDER).lower()
    if name == "openai":
        return settings.MODEL_OPENAI_MODEL
    if name in {"ali", "dashscope", "tongyi", "qwen"}:
        # API Key 池 extra.model 为主；这里提供兜底展示值
        return "qwen-plus"
    if name in {"moonshot", "kimi"}:
        return getattr(settings, "MODEL_MOONSHOT_MODEL", None) or "kimi-k2-turbo-preview"
    if name == "deepseek":
        return settings.MODEL_DEEPSEEK_MODEL
    if name in {"baidu", "wenxin", "qianfan"}:
        return os.getenv("MODEL_BAIDU_MODEL") or "ernie-5.0-thinking-latest"
    return None
