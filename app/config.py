from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    rabbitmq_url: str

    # Object storage (AWS S3 by default; set S3_ENDPOINT_URL for R2/MinIO/etc.)
    s3_bucket: str
    s3_region: str = "eu-central-1"
    s3_access_key: str
    s3_secret_key: str
    s3_endpoint_url: str | None = None

    # Uploads
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB


settings = Settings()