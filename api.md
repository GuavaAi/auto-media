# API 文档

本文档整理当前已实现的后端 API（与代码同步更新）。

---

## 已有 API

- 数据源管理：
  - `GET /api/datasources` 列表
  - `POST /api/datasources` 新增 `{name, source_type, config}`
  - `POST /api/datasources/{id}/trigger` 手动触发采集（URL 抓取 + 抽取/清洗 + 入库）
- 抓取记录：
  - `GET /api/crawl-records` 列表（含 datasource_name、content_preview、extra）
  - `GET /api/crawl-records/{id}` 详情（含完整 content + extra）
- 每日热点榜单：
  - `POST /api/daily-hotspots/build?day=YYYY-MM-DD&limit=20` 生成某日榜单（幂等）
  - `GET /api/daily-hotspots/?day=YYYY-MM-DD&limit=20` 查询某日榜单
  - `GET /api/daily-hotspots/{event_id}` 事件详情（要点 bullets + 引用 quotes + 来源 sources）
- 软文生成与查询：
  - `POST /api/generate/article` 生成软文（支持 topic/outline/keywords/tone/length/temperature/max_tokens/call_to_action/sources/summary_hint/provider）
  - `GET /api/generate/articles` 列表
  - `GET /api/generate/articles/{id}` 详情
  - `PATCH /api/generate/articles/{id}` 更新文章（编辑保存）
  - `DELETE /api/generate/articles/{id}` 删除文章
  - `POST /api/generate/articles/{id}/ai-edit` AI 重写/续写/翻译（不自动保存）

  - `ai-edit` 请求体说明：
    - `action`：`rewrite` / `continue` / `translate`
    - `selected_text`：用户选中的文本片段（**默认必填**；后端不会回退整篇文章）
      - 例外：当 `action=continue` 且提供了 `instruction` 时，允许 `selected_text` 为空（等价于从光标处开始续写）
    - `instruction`：可选，额外要求（风格、方向、限制等）
    - `target_language`：仅 `translate` 需要
    - `provider/temperature/max_tokens/length`：可选，模型与生成参数

  - `ai-edit` 示例：

    ```json
    {
      "action": "rewrite",
      "selected_text": "这是一段需要重写的文案...",
      "instruction": "更专业、结构更清晰",
      "provider": "deepseek"
    }
    ```

- 素材库（素材包/素材条目）：
  - `POST /api/materials/packs` 创建素材包
  - `GET /api/materials/packs?keyword=&limit=&offset=` 素材包列表（分页/搜索）
  - `GET /api/materials/packs/{id}` 素材包详情（含条目列表）
  - `POST /api/materials/packs/{id}/items/batch` 批量追加条目
  - `PATCH /api/materials/items/{id}` 更新条目
  - `DELETE /api/materials/items/{id}` 删除条目
  - `GET /api/materials/items/search?q=&pack_id=&limit=&offset=` 条目搜索
  - `POST /api/materials/packs/{id}/dedupe` 素材包去重（按文本规范化 hash）
