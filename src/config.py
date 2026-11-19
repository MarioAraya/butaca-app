from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_path: str = "data/cinepolis.db"
    scrape_delay_seconds: int = 20
    scrape_cron_hour: int = 6
    scrape_cron_minute: int = 0
    api_admin_key: str = "change-me-in-production"
    omdb_api_key: str = ""
    # Optional: POSTed a plain-text message when a scrape doesn't finish with
    # status "success". Works with ntfy (https://ntfy.sh/<topic>) or any endpoint
    # that accepts a text body. Empty = alerts disabled.
    alert_webhook_url: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
