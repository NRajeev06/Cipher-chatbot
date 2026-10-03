import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings:
    @property
    def GROQ_API_KEY(self) -> str:
        return os.getenv("GROQ_API_KEY", "").strip().strip('"').strip("'")

    @property
    def GROQ_CHAT_MODEL(self) -> str:
        return os.getenv("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile").strip()
    
    # Tavily Search API configuration
    @property
    def TAVILY_API_KEY(self) -> str:
        return os.getenv("TAVILY_API_KEY", "").strip().strip('"').strip("'")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cipher_db")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "cipher_super_secret_jwt_key_2026_matrix")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # Hugging Face (Image Generation)
    HF_TOKEN: str = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN", ""))
    HUGGINGFACE_TOKEN: str = HF_TOKEN
    HF_IMAGE_MODEL: str = os.getenv("HF_IMAGE_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")

    # Email & SMTP configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", os.getenv("SMTP_USER", "noreply@cipher.ai"))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Rate Limiting configuration
    CHAT_RATE_LIMIT: str = os.getenv("CHAT_RATE_LIMIT", "20/minute")
    IMAGE_RATE_LIMIT: str = os.getenv("IMAGE_RATE_LIMIT", "10/hour")
    UPLOAD_RATE_LIMIT: str = os.getenv("UPLOAD_RATE_LIMIT", "5/hour")
    LOGIN_RATE_LIMIT: str = os.getenv("LOGIN_RATE_LIMIT", "5/15minutes")
    SIGNUP_RATE_LIMIT: str = os.getenv("SIGNUP_RATE_LIMIT", "3/hour")
    RESEND_RATE_LIMIT: str = os.getenv("RESEND_RATE_LIMIT", "3/hour")

settings = Settings()
