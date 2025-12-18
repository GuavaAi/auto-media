from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

router = APIRouter()


def _load_project_markdown(*, filename: str, not_found_msg: str, read_fail_prefix: str) -> PlainTextResponse:
    md_path: Path | None = None
    for p in Path(__file__).resolve().parents:
        cand = p / filename
        if cand.exists():
            md_path = cand
            break
    if md_path is None:
        raise HTTPException(status_code=404, detail=not_found_msg)

    try:
        content = md_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{read_fail_prefix}：{exc}") from exc

    return PlainTextResponse(content=content, media_type="text/markdown; charset=utf-8")


@router.get("/user-guide", response_class=PlainTextResponse, summary="运营手册（Markdown 原文）")
def get_user_guide_markdown() -> PlainTextResponse:
    # 中文说明：项目根目录下的运营手册.md 作为单一事实来源，前端动态读取渲染
    return _load_project_markdown(
        filename="运营手册.md",
        not_found_msg="运营手册.md 不存在",
        read_fail_prefix="读取运营手册失败",
    )


@router.get("/config-guide", response_class=PlainTextResponse, summary="配置教程（Markdown 原文）")
def get_config_guide_markdown() -> PlainTextResponse:
    # 中文说明：项目根目录下的配置教程.md 作为单一事实来源，前端动态读取渲染
    return _load_project_markdown(
        filename="配置教程.md",
        not_found_msg="配置教程.md 不存在",
        read_fail_prefix="读取配置教程失败",
    )
