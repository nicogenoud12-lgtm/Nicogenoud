from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "production"
    tz: str = "America/Argentina/Buenos_Aires"
    sqlite_path: str = "/data/app.db"
    cors_origins: str = "http://localhost:8080"

    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    jwt_expires_min: int = 60
    admin_username: str = "nico"
    admin_password: str = "change-me"

    fernet_key: str = ""

    iol_base_url: str = "https://api.invertironline.com"
    iol_token_path: str = "/token"
    iol_http_timeout: int = 20

    dolarapi_base: str = "https://dolarapi.com/v1"
    default_dolar_source: str = "MEP"

    scheduler_enabled: bool = True
    snapshot_cron: str = "55 23 * * *"
    dolar_cron_morning: str = "0 8 * * *"
    dolar_cron_evening: str = "50 23 * * *"
    operations_year: int = 2026

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
