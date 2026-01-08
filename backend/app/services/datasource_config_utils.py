from __future__ import annotations

from typing import Any


def is_list_page_datasource(cfg: dict | None) -> bool:
    """判断数据源是否为“列表页/聚合页数据源”。

    中文说明：
    - 不改采集层，只根据 DataSource.config 做一个稳定、可解释的判定。
    - 经验规则：若配置了 sub_parser（抓子页面正文），或启用了动态发现子页面且 max_sub_links>0，则认为父页面是列表页。
    """

    cfg = cfg if isinstance(cfg, dict) else {}

    sub_parser = cfg.get("sub_parser")
    if isinstance(sub_parser, dict):
        css = sub_parser.get("css_selector")
        if isinstance(css, str) and css.strip():
            return True

    auto_discover_sub = cfg.get("auto_discover_sub")
    max_sub_links = cfg.get("max_sub_links")

    # 中文说明：auto_discover_sub 在抓取逻辑里可能默认 True，因此这里要求 max_sub_links>0 作为补充条件
    if auto_discover_sub is True:
        try:
            m = int(max_sub_links)
        except Exception:
            m = 0
        if m > 0:
            return True

    return False


def is_subpage_record(extra: Any) -> bool:
    """判断采集记录是否为“子页面（详情页）”。"""

    if not isinstance(extra, dict):
        return False
    return extra.get("is_discovered") is True
