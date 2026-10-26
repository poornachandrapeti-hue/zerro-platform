from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Zerro-R-vision-360 API"
    database_url: str = "sqlite:///./zerro_dashboard.db"
    frontend_origins: str = "http://localhost:5173"
    command_center_sso_secret: str = ""
    vision360_source_url: str = ""
    vision360_service_key: str = ""
    command_center_cookie_secure: bool = True
    command_center_expected_org: str = ""
    command_center_identity_url: str = ""
    command_center_identity_service_key: str = ""
    command_center_authoritative_projects: bool = True
    command_center_project_map: str = "{}"  # JSON: {"SITEFORGE_CODE":"CC_CODE"}; explicit mapping only

    command_center_approved_baseline_path: str = ""  # Server-side JSON path; empty disables approved comparison
    command_center_delay_threshold_pp: float = 10.0
    command_center_discipline_map: str = "{}"  # JSON: {"Civil":"CIVIL"}; names must be verified manually

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

