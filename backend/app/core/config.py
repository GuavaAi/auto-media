import os
from functools import lru_cache

from dotenv import load_dotenv


# 预加载 .env 文件，便于本地开发
load_dotenv()


class Settings:
    """全局配置，集中管理环境变量"""

    def __init__(self) -> None:
        self.PROJECT_NAME: str = os.getenv("PROJECT_NAME", "auto-media")
        self.ENV: str = os.getenv("ENV", "dev")

        self.MYSQL_URL: str = os.getenv(
            "MYSQL_URL",
            "mysql+pymysql://root:password@127.0.0.1:3306/auto_media?charset=utf8mb4",
        )
        self.REDIS_URL: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

        self.CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", self.REDIS_URL)
        self.CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", self.REDIS_URL)
        self.CELERY_TIMEZONE: str = os.getenv("CELERY_TIMEZONE", "Asia/Shanghai")
        self.CELERY_ALWAYS_EAGER: bool = os.getenv("CELERY_ALWAYS_EAGER", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        self.DAILY_HOTSPOT_BEAT_ENABLED: bool = os.getenv(
            "DAILY_HOTSPOT_BEAT_ENABLED", "false"
        ).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.DAILY_HOTSPOT_CRON: str = os.getenv("DAILY_HOTSPOT_CRON", "5 2 * * *")
        self.DAILY_HOTSPOT_LIMIT: int = int(os.getenv("DAILY_HOTSPOT_LIMIT", "20"))
        self.DAILY_HOTSPOT_DAY_OFFSET: int = int(os.getenv("DAILY_HOTSPOT_DAY_OFFSET", "-1"))

        # Morning Brief (Scenario C)
        self.MORNING_BRIEF_ENABLED: bool = os.getenv(
            "MORNING_BRIEF_ENABLED", "false"
        ).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.MORNING_BRIEF_CRON: str = os.getenv("MORNING_BRIEF_CRON", "0 7 * * *")

        self.DEFAULT_MODEL_PROVIDER: str = os.getenv("DEFAULT_MODEL_PROVIDER", "deepseek")
        self.MODEL_API_KEY_OPENAI: str | None = os.getenv("MODEL_API_KEY_OPENAI")
        self.MODEL_API_KEY_ALI: str | None = os.getenv("MODEL_API_KEY_ALI")
        self.MODEL_API_KEY_BAIDU: str | None = os.getenv("MODEL_API_KEY_BAIDU")
        self.MODEL_API_KEY_DEEPSEEK: str | None = os.getenv("MODEL_API_KEY_DEEPSEEK")
        self.MODEL_API_KEY_MOONSHOT: str | None = os.getenv("MODEL_API_KEY_MOONSHOT")

        self.MODEL_OPENAI_MODEL: str | None = os.getenv("MODEL_OPENAI_MODEL")
        self.MODEL_OPENAI_API_BASE: str | None = os.getenv("MODEL_OPENAI_API_BASE")
        self.MODEL_OPENAI_TIMEOUT: int = int(os.getenv("MODEL_OPENAI_TIMEOUT", "60"))
        self.MODEL_OPENAI_VERIFY: bool = os.getenv("MODEL_OPENAI_VERIFY", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        # Azure OpenAI（Chat Completions）
        self.MODEL_API_KEY_AZURE_OPENAI: str | None = os.getenv("MODEL_API_KEY_AZURE_OPENAI")
        self.MODEL_AZURE_OPENAI_ENDPOINT: str | None = os.getenv("MODEL_AZURE_OPENAI_ENDPOINT")
        self.MODEL_AZURE_OPENAI_DEPLOYMENT: str | None = os.getenv("MODEL_AZURE_OPENAI_DEPLOYMENT")
        self.MODEL_AZURE_OPENAI_API_VERSION: str | None = os.getenv("MODEL_AZURE_OPENAI_API_VERSION")
        self.MODEL_AZURE_OPENAI_TIMEOUT: int = int(os.getenv("MODEL_AZURE_OPENAI_TIMEOUT", "60"))
        self.MODEL_AZURE_OPENAI_VERIFY: bool = os.getenv("MODEL_AZURE_OPENAI_VERIFY", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.MODEL_DEEPSEEK_MODEL: str = os.getenv("MODEL_DEEPSEEK_MODEL", "deepseek-chat")
        self.MODEL_DEEPSEEK_API_BASE: str = os.getenv(
            "MODEL_DEEPSEEK_API_BASE", "https://api.deepseek.com"
        )
        self.MODEL_DEEPSEEK_VERIFY: bool = os.getenv(
            "MODEL_DEEPSEEK_VERIFY", "true"
        ).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.MODEL_DEEPSEEK_TIMEOUT: int = int(os.getenv("MODEL_DEEPSEEK_TIMEOUT", "60"))

        # Moonshot(Kimi)（OpenAI compatible）
        self.MODEL_MOONSHOT_MODEL: str | None = os.getenv("MODEL_MOONSHOT_MODEL")
        self.MODEL_MOONSHOT_API_BASE: str | None = os.getenv("MODEL_MOONSHOT_API_BASE")

        self.GENERATION_TONE: str = os.getenv("GENERATION_TONE", "专业且亲和")
        self.GENERATION_LENGTH: int = int(os.getenv("GENERATION_LENGTH", "800"))

        # 生成调试：打印分层摘要抽取结果与最终 Prompt（注意：会输出较多日志）
        self.GENERATION_DEBUG: bool = os.getenv("GENERATION_DEBUG", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.GENERATION_DEBUG_PROMPT_MAX_CHARS: int = int(
            os.getenv("GENERATION_DEBUG_PROMPT_MAX_CHARS", "4000")
        )
        self.GENERATION_DEBUG_COMPRESS_RAW_MAX_CHARS: int = int(
            os.getenv("GENERATION_DEBUG_COMPRESS_RAW_MAX_CHARS", "1200")
        )

        # 素材分层摘要（方案C）：生成前对超长素材做关键内容提取与压缩
        self.MATERIAL_COMPRESS_CHAR_THRESHOLD: int = int(
            os.getenv("MATERIAL_COMPRESS_CHAR_THRESHOLD", "1800")
        )
        self.MATERIAL_COMPRESS_BRIEF_MAX_CHARS: int = int(
            os.getenv("MATERIAL_COMPRESS_BRIEF_MAX_CHARS", "180")
        )
        self.MATERIAL_COMPRESS_BULLET_COUNT: int = int(
            os.getenv("MATERIAL_COMPRESS_BULLET_COUNT", "6")
        )


@lru_cache
def get_settings() -> Settings:
    """单例化配置，避免重复解析"""
    return Settings()
