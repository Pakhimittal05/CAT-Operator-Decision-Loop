"""Application configuration via Pydantic BaseSettings."""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


# Resolve project paths relative to this file
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DB_PATH = _BACKEND_DIR / "cat_decision_loop.db"
_DEFAULT_MODELS_DIR = _BACKEND_DIR / "models"


class Settings(BaseSettings):
    """Central configuration.  All values can be overridden with env-vars."""

    # Database
    database_url: str = f"sqlite:///{_DEFAULT_DB_PATH}"

    # Trained model artifacts
    models_dir: Path = _DEFAULT_MODELS_DIR

    # Demo mode flag — controls seed-data behaviours
    demo_mode: bool = True

    # Safety thresholds
    seatbelt_unengaged_threshold_seconds: float = 5.0
    proximity_safe_distance_meters: float = 5.0

    model_config = {"env_prefix": "CAT_"}


settings = Settings()
