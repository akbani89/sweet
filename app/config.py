from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    OTP_EXPIRE_MINUTES: int = 10
    DEV_MODE: bool = True  # Returns OTP in API response — disable in prod

    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    LOCAL_UPLOAD_DIR: str = "uploads"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET: str = ""
    AWS_REGION: str = "us-east-1"
    R2_ENDPOINT_URL: str = ""  # Cloudflare R2 endpoint if using R2

    class Config:
        env_file = ".env"


settings = Settings()
