import json
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationType(Enum):
    BEAR = "bear"
    ARENA = "arena"
    EVENT = "event"

@dataclass
class BearPingSettings:
    incoming_enabled: bool = True
    pre_attack_enabled: bool = True
    pre_attack_offset: int = 10

@dataclass
class ArenaPingSettings:
    ping_enabled: bool = True
    ping_offset: int = 10

@dataclass
class EventPingSettings:
    reminder_enabled: bool = True
    reminder_offset: int = 60
    final_call_enabled: bool = True
    final_call_offset: int = 10

class ConfigValidationError(Exception):
    """Raised when config validation fails"""
    pass

def _load_config() -> Dict[str, Any]:
    """Load the bot config file"""
    try:
        with open('bot_config_dev.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Config file not found")
        raise
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config file")
        raise

def _save_config(config: Dict[str, Any]) -> None:
    """Save the bot config file"""
    try:
        with open('bot_config_dev.json', 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        raise

def _validate_offset(offset: int, min_val: int = 1, max_val: int = 60) -> None:
    """Validate that an offset is within allowed range"""
    if not min_val <= offset <= max_val:
        raise ConfigValidationError(f"Offset must be between {min_val} and {max_val} minutes")

def _validate_chronological_order(settings: Dict[str, Any], notification_type: NotificationType) -> None:
    """Validate that notification phases maintain chronological order"""
    if notification_type == NotificationType.BEAR:
        if settings.get("pre_attack_enabled", True):
            _validate_offset(settings.get("pre_attack_offset", 10))
    elif notification_type == NotificationType.EVENT:
        reminder_offset = settings.get("reminder_offset", 60)
        final_call_offset = settings.get("final_call_offset", 10)
        if settings.get("reminder_enabled", True) and settings.get("final_call_enabled", True):
            if reminder_offset <= final_call_offset:
                raise ConfigValidationError("Reminder offset must be greater than final call offset")
            if reminder_offset - final_call_offset < 5:
                raise ConfigValidationError("Minimum gap between notifications must be 5 minutes")

def _ensure_notification_settings(config: Dict[str, Any], guild_id: str, notification_type: NotificationType) -> None:
    """Ensure notification settings exist in config for a guild"""
    if guild_id not in config:
        config[guild_id] = {}
    
    guild_config = config[guild_id]
    
    if notification_type.value not in guild_config:
        guild_config[notification_type.value] = {}
    
    if "ping_settings" not in guild_config[notification_type.value]:
        if notification_type == NotificationType.BEAR:
            guild_config[notification_type.value]["ping_settings"] = {
                "incoming_enabled": True,
                "pre_attack_enabled": True,
                "pre_attack_offset": 10
            }
        elif notification_type == NotificationType.ARENA:
            guild_config[notification_type.value]["ping_settings"] = {
                "ping_enabled": True,
                "ping_offset": 10
            }
        elif notification_type == NotificationType.EVENT:
            guild_config[notification_type.value]["ping_settings"] = {
                "reminder_enabled": True,
                "reminder_offset": 60,
                "final_call_enabled": True,
                "final_call_offset": 10
            }

# Bear notification helpers
def get_bear_ping_settings(guild_id: str) -> BearPingSettings:
    """Get bear notification settings for a guild"""
    config = _load_config()
    _ensure_notification_settings(config, guild_id, NotificationType.BEAR)
    
    settings = config[guild_id]["bear"]["ping_settings"]
    return BearPingSettings(
        incoming_enabled=settings.get("incoming_enabled", True),
        pre_attack_enabled=settings.get("pre_attack_enabled", True),
        pre_attack_offset=settings.get("pre_attack_offset", 10)
    )

def update_bear_ping_setting(guild_id: str, key: str, value: Any) -> None:
    """Update a bear notification setting"""
    config = _load_config()
    _ensure_notification_settings(config, guild_id, NotificationType.BEAR)
    
    settings = config[guild_id]["bear"]["ping_settings"]
    
    if key == "pre_attack_offset":
        _validate_offset(value)
    elif key not in ["incoming_enabled", "pre_attack_enabled"]:
        raise ConfigValidationError(f"Invalid setting key: {key}")
    
    settings[key] = value
    
    # Validate chronological order after update
    _validate_chronological_order(settings, NotificationType.BEAR)
    
    _save_config(config)
    logger.info(f"Updated bear ping setting for guild {guild_id}: {key}={value}")

# Arena notification helpers
def get_arena_ping_settings(guild_id: str) -> ArenaPingSettings:
    """Get arena notification settings for a guild"""
    config = _load_config()
    _ensure_notification_settings(config, guild_id, NotificationType.ARENA)
    
    settings = config[guild_id]["arena"]["ping_settings"]
    return ArenaPingSettings(
        ping_enabled=settings.get("ping_enabled", True),
        ping_offset=settings.get("ping_offset", 10)
    )

def update_arena_ping_setting(guild_id: str, key: str, value: Any) -> None:
    """Update an arena notification setting"""
    config = _load_config()
    _ensure_notification_settings(config, guild_id, NotificationType.ARENA)
    
    settings = config[guild_id]["arena"]["ping_settings"]
    
    if key == "ping_offset":
        _validate_offset(value)
    elif key != "ping_enabled":
        raise ConfigValidationError(f"Invalid setting key: {key}")
    
    settings[key] = value
    _save_config(config)
    logger.info(f"Updated arena ping setting for guild {guild_id}: {key}={value}")

# Event notification helpers
def get_event_ping_settings(guild_id: str) -> EventPingSettings:
    """Get event notification settings for a guild"""
    config = _load_config()
    _ensure_notification_settings(config, guild_id, NotificationType.EVENT)
    
    settings = config[guild_id]["event"]["ping_settings"]
    return EventPingSettings(
        reminder_enabled=settings.get("reminder_enabled", True),
        reminder_offset=settings.get("reminder_offset", 60),
        final_call_enabled=settings.get("final_call_enabled", True),
        final_call_offset=settings.get("final_call_offset", 10)
    )

def update_event_ping_setting(guild_id: str, key: str, value: Any) -> None:
    """Update an event notification setting"""
    config = _load_config()
    _ensure_notification_settings(config, guild_id, NotificationType.EVENT)
    
    settings = config[guild_id]["event"]["ping_settings"]
    
    if key in ["reminder_offset", "final_call_offset"]:
        _validate_offset(value)
    elif key not in ["reminder_enabled", "final_call_enabled"]:
        raise ConfigValidationError(f"Invalid setting key: {key}")
    
    settings[key] = value
    
    # Validate chronological order after update
    _validate_chronological_order(settings, NotificationType.EVENT)
    
    _save_config(config)
    logger.info(f"Updated event ping setting for guild {guild_id}: {key}={value}")

def get_all_ping_settings(guild_id: str) -> Dict[str, Any]:
    """Get all notification settings for a guild"""
    return {
        "bear": get_bear_ping_settings(guild_id).__dict__,
        "arena": get_arena_ping_settings(guild_id).__dict__,
        "event": get_event_ping_settings(guild_id).__dict__
    } 