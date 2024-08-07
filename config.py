from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TG_API: str
    WEBHOOK_HOST: str
    WEBHOOK_PATH: str
    WEBAPP_HOST: str
    WEBAPP_PORT: int
    OPENAI_API_KEY: str
    OPENAI_TTS_URL: str

    class Config:
        env_file = ".env"


settings = Settings()
