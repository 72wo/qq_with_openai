import json
import os
from pathlib import Path
from typing import Any, Dict

class Config:
    def __init__(self, config_path: str = "backend/config/default_config.json"):
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from JSON file, create default if not exists."""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self._create_default_config()

    def _create_default_config(self):
        """Create default configuration structure."""
        self.config = {
            "openai": {
                "baseurl": "",
                "apikey": "",
                "model": "gpt-4",
                "vision_enabled": False
            },
            "bot": {
                "prompt": "你是一个有帮助的 AI 助手",
                "auto_reply": True,
                "group_only_at": True
            },
            "blacklist": {
                "mode": "enabled",
                "users": [],
                "groups": [],
                "exceptions": []
            },
            "whitelist": {
                "mode": "disabled",
                "users": [],
                "groups": [],
                "exceptions": []
            },
            "features": {
                "image_processing": True,
                "emotion_conversion": True
            },
            "advanced": {
                "napcat_url": "ws://localhost:8080/ws/napcat",
                "napcat_token": "",
                "service_port": 5000,
                "log_level": "INFO"
            }
        }
        self.save_config()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation (e.g., 'openai.apikey')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """Set configuration value by dot notation."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration."""
        return self.config

    def save_config(self):
        """Save configuration to JSON file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def update_config(self, new_config: Dict[str, Any]):
        """Update entire configuration."""
        self.config = new_config
        self.save_config()
