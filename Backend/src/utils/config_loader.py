import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

def load_yaml(filename: str) -> dict:

    """Load the specified yaml file from the config directory.
    
        Args:
            filename: name of the yaml file.

    """

    config_path = Path(__file__).parent.parent.parent / "config" / filename
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def get_env(key: str, default: str = "") -> str:

    """Utility function for load environment variables from the .env file"""

    load_dotenv()
    return os.getenv(key, default)


def get_jwt_settings() -> dict:

    """Load JWT configuration from environment"""

    return {
        "secret_key": get_env("JWT_SECRET", "dev-secret-change-in-prod"),
        "algorithm": get_env("JWT_ALGORITHM", "HS256"),
        "access_token_expire_minutes": int(get_env("JWT_EXPIRY_MINUTES", "600")),
    }