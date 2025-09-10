from pydantic import BaseModel, Field
from typing import Optional

class GeneralSettings(BaseModel):
    bot_token: str = Field("", description="Discord bot token")
    timezone: str = Field("Europe/Stockholm")
    update_seconds: int = Field(60, ge=10, le=3600)
    stats_update_seconds: int = Field(86400, ge=300, le=604800)
    qb_update_seconds: int = Field(120, ge=10, le=3600)
    plex_update_seconds: int = 3600
    message_id_file: str = Field("/data/message_ids.json")

class PlexStreamsSettings(BaseModel):
    channel_id: Optional[int] = Field(None, description="Discord channel for Plex streams")
    post_thumbnails: bool = True

class PlexChannels(BaseModel):
    movies_channel: Optional[int] = None
    tv_shows_channel: Optional[int] = None
    user_count_channel: Optional[int] = None

class StatisticsSettings(BaseModel):
    channel_id: Optional[int] = Field(None, description="Discord channel for daily stats (omit to disable)")

class ArrSettings(BaseModel):
    radarr_host: Optional[str] = None
    radarr_api_key: Optional[str] = None
    sonarr_host: Optional[str] = None
    sonarr_api_key: Optional[str] = None

class QbitSettings(BaseModel):
    host: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    channel_id: Optional[int] = None

class Settings(BaseModel):
    general: GeneralSettings = GeneralSettings()
    streams: PlexStreamsSettings = PlexStreamsSettings()
    plex_channels: PlexChannels = PlexChannels()
    stats: StatisticsSettings = StatisticsSettings()
    arr: ArrSettings = ArrSettings()
    qbit: QbitSettings = QbitSettings()

    # Tautulli (required for streams/stats)
    tautulli_url: str = ""
    tautulli_api_key: str = ""

