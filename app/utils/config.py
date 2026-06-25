from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Smart CCTV Face Recognition"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "dev-secret"

    host: str = "127.0.0.1"
    port: int = 8000

    db_driver: Literal["sqlite", "mysql"] = "sqlite"
    database_url: str | None = None

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "smart_cctv"

    camera_source: str = "0"
    face_model: str = "Facenet"
    recognition_threshold: float = 0.55
    detection_interval: float = 1.0
    attendance_interval: float = 300.0
    rtsp_url: str = ""

    dataset_dir: str = "datasets"
    screenshot_dir: str = "screenshots"
    log_dir: str = "logs"

    session_max_age: int = 86400
    admin_username: str = "admin"
    admin_password: str = ""

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.db_driver == "mysql":
            user = quote_plus(self.db_user)
            password = quote_plus(self.db_password)
            return (
                f"mysql+pymysql://{user}:{password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
                f"?charset=utf8mb4"
            )
        return f"sqlite:///{Path('database/smart_cctv.db').resolve()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
