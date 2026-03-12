from dataclasses import dataclass, asdict
from pathlib import Path
import json


@dataclass
class Settings:
    worker_pool_size: int = 1
    poll_interval: float = 3.0
    generate_timeout: int = 300
    output_dir: str = "output"
    headless: bool = True

    def validate(self):
        if self.worker_pool_size <= 0:
            raise ValueError("worker_pool_size must be > 0")

        if self.poll_interval <= 0:
            raise ValueError("poll_interval must be > 0")

        if self.generate_timeout < 10:
            raise ValueError("generate_timeout must be >= 10")

        if not self.output_dir:
            raise ValueError("output_dir cannot be empty")


def load(settings_file="settings.json"):
    p = Path(settings_file)

    if not p.exists():
        return Settings()

    try:
        data = json.loads(p.read_text())
    except Exception:
        return Settings()

    valid_keys = Settings().__dict__.keys()
    filtered = {k: v for k, v in data.items() if k in valid_keys}

    return Settings(**filtered)


def save(settings: Settings, settings_file="settings.json"):
    if not isinstance(settings, Settings):
        raise ValueError("invalid settings")

    settings.validate()

    p = Path(settings_file)

    with open(p, "w", encoding="utf8") as f:
        json.dump(asdict(settings), f, indent=2)

