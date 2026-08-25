import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Configuration read from environment variables, never hard-coded secrets."""

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173")

    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DATABASE_URL is required. Copy .env.example to .env and set it."
        )
