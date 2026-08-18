"""
config.py — Application settings loaded from environment variables.

All settings have documented defaults except DATABASE_URL, which must be
provided via the environment (or .env file). This makes the application
deployment-agnostic: no hard-coded credentials, no environment-specific code.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ------------------------------------------------------------------
    # Database
    # Required. Format: postgresql+asyncpg://user:password@host/dbname
    # Neon example: postgresql+asyncpg://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb
    # ------------------------------------------------------------------
    database_url: str

    # ------------------------------------------------------------------
    # API behaviour
    # ------------------------------------------------------------------
    # Comma-separated origins, or "*" for open access (acceptable for demo)
    cors_origins: str = "*"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = "INFO"

    # ------------------------------------------------------------------
    # Scheduler
    # Set to false to disable background polling (manual trigger still works)
    # ------------------------------------------------------------------
    scheduler_enabled: bool = True

    # How often to poll the Remotive RSS feed (minimum: avoids hammering the source)
    remotive_interval_minutes: int = 30

    # ------------------------------------------------------------------
    # Manual trigger cooldown
    # Prevents accidental double-triggers in the demo UI
    # ------------------------------------------------------------------
    trigger_cooldown_seconds: int = 60

    # ------------------------------------------------------------------
    # HTTP fetch settings
    # ------------------------------------------------------------------
    # Separate connect and read timeouts give better failure diagnostics
    fetch_timeout_connect: float = 5.0   # seconds to establish TCP connection
    fetch_timeout_read: float = 10.0     # seconds to receive the full response body

    # How many times to retry a failed request (after the initial attempt)
    fetch_max_retries: int = 3

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------
    # How many consecutive adapter failures open the circuit
    circuit_failure_threshold: int = 5

    # How many seconds the circuit stays OPEN before attempting a probe
    circuit_open_wait_seconds: int = 300

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        # Allows DATABASE_URL or database_url in .env (case-insensitive)
        "case_sensitive": False,
    }


# Single shared instance — imported by all modules that need settings
settings = Settings()
