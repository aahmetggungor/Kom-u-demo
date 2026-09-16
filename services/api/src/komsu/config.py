from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChannelConnectorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")
    tenant_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    actor_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    source: Literal["sms", "messaging", "social", "phone"]
    secret: SecretStr = Field(min_length=32, max_length=256, repr=False)
    requests_per_minute: int = Field(default=120, ge=1, le=10_000)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KOMSU_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./komsu.db"
    environment: str = "development"
    allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    max_body_bytes: int = Field(default=32768, ge=1024, le=1048576)
    max_audio_bytes: int = Field(default=2_000_000, ge=6400, le=5_000_000)
    max_inbound_bytes: int = Field(default=2_800_000, ge=32768, le=7_000_000)
    audio_master_key_b64: str | None = Field(default=None, repr=False)
    audio_key_id: str = Field(default="development-audio-v1", min_length=1, max_length=80)
    requests_per_minute: int = Field(default=120, ge=1)
    queue_limit: int = Field(default=10000, ge=1)
    geocoder_url: str | None = None
    map_package_manifest: str | None = Field(default=None, max_length=500)
    channel_connectors: list[ChannelConnectorSettings] = Field(default_factory=list)
    embedding_revision: str | None = Field(default=None, max_length=160)
    translation_model_dir: str | None = Field(default=None, max_length=500)
    whisper_model_dir: str | None = Field(default=None, max_length=500)
    worker_metrics_port: int | None = Field(default=None, ge=1024, le=65535)

    def validate_runtime(self) -> None:
        if self.environment not in {"development", "test"}:
            raise ValueError(
                "Pilot/production mode is gated pending security and operational validation"
            )
