"""Environment-only configuration; invalid settings fail at startup."""
import os
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Settings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    market_timeout_seconds: float = Field(default=10, gt=0, le=60)
    cache_ttl_seconds: float = Field(default=300, ge=0, le=86400)
    cache_max_entries: int = Field(default=128, ge=1, le=2048)
    cors_origins: list[str] = Field(default_factory=list)
    database_url: SecretStr | None = None

    @classmethod
    def from_env(cls):
        values = {}
        for name in cls.model_fields:
            raw = os.getenv(f'MARKETLENS_{name.upper()}')
            if raw is not None:
                values[name] = ([part.strip() for part in raw.split(',') if part.strip()]
                                if name == 'cors_origins' else raw)
        return cls(**values)
