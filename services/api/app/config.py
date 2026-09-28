"""应用配置。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DREAMSPACE_", env_file=".env", extra="ignore"
    )

    app_name: str = "dreamspace-api"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8000

    # 数据与文件
    data_dir: Path = Path("data")
    books_dir: Path | None = None
    artifacts_dir: Path | None = None

    # 造梦 skill 位置（当前工作区为仓库克隆 zaomeng/；设计上 vendor/zaomeng 为 submodule）
    zaomeng_skill_root: Path = Path("zaomeng/zaomeng-skill")

    # LLM（OpenAI 兼容）
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # 存储
    store: str = "sqlite"  # sqlite | memory
    db_path: Path | None = None

    @property
    def resolved_db_path(self) -> Path:
        return self.db_path or (self.data_dir / "dreamspace.db")

    @property
    def resolved_books_dir(self) -> Path:
        return self.books_dir or (self.data_dir / "books")

    @property
    def resolved_artifacts_dir(self) -> Path:
        return self.artifacts_dir or (self.data_dir / "artifacts")


@lru_cache
def get_settings() -> Settings:
    return Settings()
