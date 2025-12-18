from __future__ import annotations


class PublishError(Exception):
    """发布流程统一异常。

    中文说明：
    - code 便于前端/上层区分错误类型
    - message 用于用户可读提示
    """

    def __init__(self, code: str, message: str, detail: object | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail
