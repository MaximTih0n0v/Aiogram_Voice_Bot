from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TG_API: str
    WEBHOOK_HOST: str
    WEBHOOK_PATH: str
    WEBAPP_HOST: str = '0.0.0.0'
    WEBAPP_PORT: int = 8888
    OPENAI_API_KEY: str
    OPENAI_TTS_URL: str

    class Config:
        env_file = ".env"


settings = Settings()
