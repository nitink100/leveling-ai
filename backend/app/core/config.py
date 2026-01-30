from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LevelingAI"
    env: str = "local"
    database_url: str

    model_config = SettingsConfigDict(env_file="backend/.env", extra="ignore")


settings = Settings()
