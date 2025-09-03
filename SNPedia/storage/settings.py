import json
import os
from typing import Any, Dict
from base.utils import get_default_data_dir


class Settings:
    """Manages user settings stored in JSON format."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.settings_file = os.path.join(data_dir, 'settings.json')
        self._settings = self._load_settings()
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load settings from JSON file, creating default if it doesn't exist."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading settings: {e}")
                return self._get_default_settings()
        else:
            return self._get_default_settings()
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings."""
        return {
            "show_disclaimer": True
        }
    
    def _save_settings(self) -> None:
        """Save current settings to JSON file."""
        with open(self.settings_file, 'w') as f:
            json.dump(self._settings, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save to file."""
        self._settings[key] = value
        self._save_settings()
    
    def get_show_disclaimer(self) -> bool:
        """Get the show_disclaimer setting."""
        return self.get("show_disclaimer", True)
    
    def set_show_disclaimer(self, show: bool) -> None:
        """Set the show_disclaimer setting."""
        self.set("show_disclaimer", show)


def get_settings(data_dir: str = None) -> Settings:
    """Get a Settings instance for the given data directory."""
    if data_dir is None:
        data_dir = get_default_data_dir()
    return Settings(data_dir)
