from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://siteforge:siteforge@localhost:5432/siteforge"
    )
    allowed_origins: str = "http://localhost:5173"
    cookie_secure: bool = False
    session_hours: int = 12
    command_center_sso_secret: str = ""
    command_center_identity_service_key: str = ""
    vision360_service_key: str = ""
    vision360_organization_id: int | None = None
    file_root: str = "/tmp/siteforge-files"
    max_upload_bytes: int = 5_000_000
    email_enabled: bool = False
    # Scanned drawings need an external OCR/table service. Credentials stay on the server.
    ocr_provider: str = ""
    ocr_endpoint: str = ""
    ocr_api_key: str = ""
    ocr_timeout_seconds: int = 90
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self):
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]


settings = Settings()
