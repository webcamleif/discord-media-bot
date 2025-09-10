import asyncio, logging, datetime, pytz, re
from typing import Optional, List, Dict

import discord
from discord.errors import LoginFailure

from app.config import Settings
from app.tautulli import TautulliClient
from app.store import load_message_ids, save_message_ids

log = logging.getLogger("bot")

class BotManager:
    def __init__(self):
        self.client: Optional[discord.Client] = None
        self.cfg: Optional[Settings] = None
        self._streams_task = None
        self._stats_task = None
        self._downloads_task = None
        self._plex_channels_task = None
        self._msg_ids: dict = {}
        self._posters = None
        self._tautulli: Optional[TautulliClient] = None
        self._qbit = None
        self.status: str = "stopped"   # "stopped" | "running" | "error"
        self.last_error: Optional[str] = None

    async def start(self, cfg: Settings):
        await self._start_or_reload(cfg)

    async def reload(self, cfg: Settings):
        await self._start_or_reload(cfg)

    async def _start_or_reload(self, cfg: Settings):
        # Stop any running bot
        if self.client:
            await self._stop_tasks()
            await self._close_client()

        self.cfg = cfg
        self._msg_ids = load_message_ids(self.cfg.general.message_id_file) or {}
        self._setup_optionals()
        self._setup_client()

        # Start only if token exists
        if not (self.cfg.general.bot_token or "").strip():
            self.status = "stopped"
            self.last_error = "Bot token not set"
            log.warning("Discord bot not started: missing token")
            return

        asyncio.create_task(self._run_client_and_tasks())

    def _setup_optionals(self):
        # Require Tautulli if streams or plex_channels enabled
        if (
            (self.cfg.streams.channel_id
             or (self.cfg.plex_channels and (
                 self.cfg.plex_channels.movies_channel
                 or self.cfg.plex_channels.tv_shows_channel
                 or self.cfg.plex_channels.user_count_channel)))
            and not (self.cfg.tautulli_url and self.cfg.tautulli_api_key)
        ):
            log.warning("Streams/Plex channels set but Tautulli is not configured – disabling them")
            self.cfg.streams.channel_id = None
            if self.cfg.plex_channels:
                self.cfg.plex_channels.movies_channel = None
                self.cfg.plex_channels.tv_shows_channel = None
                self.cfg.plex_channels.user_count_channel = None

        # Require qBittorrent if downloads enabled
        if self.cfg.qbit.channel_id and not (self.cfg.qbit.host and self.cfg.qbit.username and self.cfg.qbit.password):
            log.warning("qBittorrent channel is set but credentials missing – skipping downloads worker")
            self.cfg.qbit.channel_id = None
    
        # Init clients
        self._tautulli = (
            TautulliClient(self.cfg.tautulli_url, self.cfg.tautulli_api_key)
            if (self.cfg.tautulli_url and self.cfg.tautulli_api_key) else None
        )
    
        # Posters
        self._posters = None
        try:
            if ((self.cfg.arr.radarr_host and self.cfg.arr.radarr_api_key) or
                (self.cfg.arr.sonarr_host and self.cfg.arr.sonarr_api_key)):
                from app.posters import PosterResolver
                self._posters = PosterResolver(
                    self.cfg.arr.radarr_host or "",
                    self.cfg.arr.radarr_api_key or "",
                    self.cfg.arr.sonarr_host or "",
                    self.cfg.arr.sonarr_api_key or "",
                )
        except Exception as e:
            log.warning("Posters disabled: %s", e)
    
        # qBittorrent
        self._qbit = None
        if self.cfg.qbit.host and self.cfg.qbit.channel_id:
            from app.qbit import QbitClient
            self._qbit = QbitClient(self.cfg.qbit.host, 8080, self.cfg.qbit.username, self.cfg.qbit.password)

    def _setup_client(self):
        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_ready():
            log.info("Logged in as %s", self.client.user)
            self.status = "running"
            self.last_error = None
            if self.cfg.streams.channel_id and self._tautulli:
                self._streams_task = asyncio.create_task(self._streams_worker())
            if self.cfg.stats.channel_id and self._tautulli:
                self._stats_task = asyncio.create_task(self._stats_worker())
            if self.cfg.qbit.channel_id and self._qbit:
                self._downloads_task = asyncio.create_task(self._downloads_worker())
            if (
                self.cfg.plex_channels
                and (
                    self.cfg.plex_channels.movies_channel
                    or self.cfg.plex_channels.tv_shows_channel
                    or self.cfg.plex_channels.user_count_channel
                )
            ):
                self._plex_channels_task = asyncio.create_task(self._plex_channels_worker())


        @self.client.event
        async def on_disconnect():
            log.info("Discord client disconnected")

    async def _run_client_and_tasks(self):
        try:
            self.status = "running"
            await self.client.start(self.cfg.general.bot_token)
        except LoginFailure:
            self.status = "error"
            self.last_error = "Improper token has been passed."
            log.exception("Discord login failed (invalid token)")
        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            log.exception("Discord client stopped")

    async def _stop_tasks(self):
        for t in (self._streams_task, self._stats_task, self._downloads_task, self._plex_channels_task):
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
                except BaseException:
                    pass
        self._streams_task = self._stats_task = self._downloads_task = self._plex_channels_task = None

    async def _close_client(self):
        try:
            await self.client.close()
        except Exception:
            pass
        self.client = None
        self.status = "stopped"

    # ---------- Helpers ----------
    def _now_str(self) -> str:
        tz = pytz.timezone(self.cfg.general.timezone)
        now = datetime.datetime.now(tz)
        suffix = "th" if 11 <= now.day <= 13 else {1:'st',2:'nd',3:'rd'}.get(now.day % 10, 'th')
        return now.strftime(f"%d{suffix} %B %H:%M")

    def _progress_percent(self, sess: Dict) -> int:
        try:
            total = int(float(sess.get("duration", 0) or 0))
            viewed = int(float(sess.get("view_offset", 0) or 0))
            if total > 0:
                return max(0, min(100, int(round(viewed / total * 100))))
        except Exception:
            pass
        try:
            return int(round(float(sess.get("progress_percent", 0) or 0)))
        except Exception:
            return 0

    def _eta_or_left(self, sess: Dict) -> tuple[str, str]:
        def to_int(x, default=0):
            try:
                if x in (None, "", "None"): return default
                return int(float(x))
            except Exception:
                return default
        total_ms = to_int(sess.get("duration")) or to_int(sess.get("media_duration"))
        viewed_ms = to_int(sess.get("view_offset"))
        if viewed_ms <= 0 and total_ms > 0:
            try:
                viewed_ms = int(total_ms * (float(sess.get("progress_percent") or 0.0) / 100.0))
            except Exception:
                viewed_ms = 0
        if total_ms <= 0:
            return ("ETA" if str(sess.get("state","")).lower() == "playing" else "Left", "—")
        rem = max(0, (total_ms - viewed_ms)//1000)
        if str(sess.get("state","")).lower() in ("playing","buffering"):
            tz = pytz.timezone(self.cfg.general.timezone)
            eta = datetime.datetime.now(tz) + datetime.timedelta(seconds=rem)
            return ("ETA", eta.strftime("%H:%M %Z"))
        if rem <= 0:
            return ("Left", "0m left")
        h, m = rem//3600, (rem%3600)//60
        return ("Left", f"{h}h {m}m left" if h else f"{m}m left")

    def _clean_title(self, raw: str) -> str:
        """Remove common release/quality tags and group tags from titles."""
        if not raw:
            return raw
    
        cleaned = raw
    
        # 1. Remove group tags like [SubsPlease] or [Erai-raws]
        cleaned = re.sub(r'^\[[^\]]+\]\s*', '', cleaned)
    
        # 2. Remove trailing tags like [F123ABC] or [1080p]
        cleaned = re.sub(r'\[[^\]]+\]\s*$', '', cleaned)
    
        # 3. Remove episode markers like " - 06 " (only if not "SxxEyy")
        cleaned = re.sub(r'\s*-\s*\d{1,3}\s*$', '', cleaned)
    
        # 4. Remove quality/release info like 2160p, WEB-DL, HDR, Atmos, x265, REMUX, etc.
        cleaned = re.sub(
            r'\s*\(?(?:\d{3,4}p|web[- ]?dl|bluray|hdr|dv|hevc|h26[45]|atmos|ddp|aac|dts|remux|hybrid).*?\)?',
            '',
            cleaned,
            flags=re.I,
        )
    
        return cleaned.strip()

    def _resolve_poster(self, sess: Dict) -> Optional[str]:
        if not (self._posters and self.cfg.streams.post_thumbnails):
            return None
    
        media_type = sess.get("media_type") or ""
        if media_type == "episode":
            raw_title = sess.get("grandparent_title") or sess.get("title") or None
        else:
            raw_title = sess.get("title") or sess.get("full_title") or None
    
        if not raw_title:
            return None
    
        # Detect TV from Plex metadata if available
        if media_type == "episode":
            title = self._clean_title(raw_title)
            tvdb_id = sess.get("tvdb_id") or None
            try:
                return self._posters.tv_poster(title, tvdb_id)
            except Exception:
                return None
    
        # Movie logic (same as before)
        title = self._clean_title(raw_title)
        year = sess.get("year") or None
        imdb_id = sess.get("imdb_id") or None
        tmdb_id = sess.get("tmdb_id") or None
        try:
            poster = self._posters.movie_poster(title, year, imdb_id, tmdb_id)
            if not poster and title:
                poster = self._posters.movie_poster(title, None, imdb_id, tmdb_id)
            return poster
        except Exception:
            return None

    # ---------- Workers ----------
    async def _streams_worker(self):
        while not self.client.is_closed():
            try:
                sessions = await self._tautulli.get_activity() if self._tautulli else []
                embeds = self._build_stream_embeds(sessions)
                await self._post_or_edit("streams", self.cfg.streams.channel_id, embeds=embeds)
            except Exception:
                log.exception("streams worker error")
            await asyncio.sleep(self.cfg.general.update_seconds)

    async def _plex_channels_worker(self):
        # Wait until Discord client is connected and ready
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            try:
                # Fetch stats from Tautulli
                stats = await self._fetch_plex_stats()
                if stats:
                    await self._update_plex_channels(stats)
            except Exception:
                log.exception("Plex channels update failed")
            await asyncio.sleep(self.cfg.general.plex_update_seconds or 3600)

    async def _fetch_plex_stats(self):
        if not self._tautulli:
            return None
        movies = await self._tautulli.count_library("movie")
        shows = await self._tautulli.count_library("show")
        users = await self._tautulli.count_users()
        return {"movies": movies, "shows": shows, "users": users}


    async def _update_plex_channels(self, stats: dict):
        # Movies channel
        if self.cfg.plex_channels.movies_channel:
            chan = self.client.get_channel(self.cfg.plex_channels.movies_channel)
            if chan:
                try:
                    await chan.edit(name=f"🎬 Movies: {stats['movies']}")
                except Exception:
                    log.exception("Failed to update movies channel")

        # TV shows channel
        if self.cfg.plex_channels.tv_shows_channel:
            chan = self.client.get_channel(self.cfg.plex_channels.tv_shows_channel)
            if chan:
                try:
                    await chan.edit(name=f"📺 TV Shows: {stats['shows']}")
                except Exception:
                    log.exception("Failed to update TV shows channel")

        # User count channel
        if self.cfg.plex_channels.user_count_channel:
            chan = self.client.get_channel(self.cfg.plex_channels.user_count_channel)
            if chan:
                try:
                    await chan.edit(name=f"👤 Users: {stats['users']}")
                except Exception:
                    log.exception("Failed to update user count channel")

    async def _stats_worker(self):
        while not self.client.is_closed():
            try:
                tu30  = await self._tautulli.get_home_stats("top_users", 30, length=5)
                tu365 = await self._tautulli.get_home_stats("top_users", 365, length=5)
                tm30  = await self._tautulli.get_home_stats("top_movies", 30, length=5)
                tv30  = await self._tautulli.get_home_stats("top_tv", 30, length=5)
                embed = self._build_stats_embed(tu30, tu365, tm30, tv30)
                await self._post_or_edit("stats", self.cfg.stats.channel_id, embed=embed)
            except Exception:
                log.exception("stats worker error")
            await asyncio.sleep(self.cfg.general.stats_update_seconds)

    async def _downloads_worker(self):
        while not self.client.is_closed():
            try:
                torrents = self._qbit.get_downloading() if self._qbit else None
                status = self._qbit.status_text() if self._qbit else "qBittorrent not configured"
                embeds = self._build_downloads_embed(torrents, status)
                await self._post_or_edit("downloads", self.cfg.qbit.channel_id, embeds=embeds)
            except Exception:
                log.exception("downloads worker error")
            await asyncio.sleep(self.cfg.general.qb_update_seconds)

    # ---------- Builders ----------
    def _build_stream_embeds(self, sessions: List[Dict]) -> List[discord.Embed]:
        embeds: List[discord.Embed] = []
        if not sessions:
            e = discord.Embed(title="Plex Streams", description="Currently no streams active", color=0x00ff00)
            e.set_footer(text=self._now_str())
            return [e]
        # limit to 6 unless you add config.general.max_sessions
        for sess in sessions[:6]:
            color = 0xFFD700 if str(sess.get("state","")).lower() == "paused" else 0x00FF00
            e = discord.Embed(title=sess.get("full_title") or "—", description=(sess.get("summary") or "")[:1000], color=color)
            user = sess.get("friendly_name") or "—"
            status = f"{str(sess.get('state','')).capitalize()} • {self._progress_percent(sess)}%"
            lbl, val = self._eta_or_left(sess)
            decision = (sess.get("transcode_decision") or "Direct Play").capitalize()
            vcodec = (sess.get("video_codec") or "—").upper()
            vres   = sess.get("video_resolution") or ""
            vdr    = sess.get("video_dynamic_range") or ""
            stream = f"{decision} ({vcodec} {vres}{' ' + vdr if vdr else ''})".strip()

            if sess.get("media_type") == "episode":
                e.add_field(name="User", value=user, inline=True)
                e.add_field(name="Season", value=sess.get("parent_media_index") or "—", inline=True)
                e.add_field(name="Episode", value=sess.get("media_index") or "—", inline=True)
                e.add_field(name="Status", value=status, inline=True)
                e.add_field(name="Stream", value=stream, inline=True)
                e.add_field(name=lbl, value=val, inline=True)
            else:
                e.add_field(name="User", value=user, inline=True)
                e.add_field(name="Year", value=sess.get("year") or "—", inline=True)
                e.add_field(name="Status", value=status, inline=True)
                e.add_field(name="Stream", value=stream, inline=True)
                e.add_field(name=lbl, value=val, inline=True)

            poster = self._resolve_poster(sess)
            if poster:
                e.set_thumbnail(url=poster)
            e.set_footer(text=self._now_str())
            embeds.append(e)
        return embeds[:10]

    def _build_stats_embed(self, top_users_30, top_users_365, top_movies_30, top_tv_30) -> discord.Embed:
        e = discord.Embed(title="Top Activity (Daily)", color=0x6a0dad)
        def fmt(rows, key="title"):
            if not rows: return "—"
            return "\n".join(f"{i}. {(r.get(key) or r.get('user') or '—')} — {r.get('total_plays',0)} plays"
                             for i, r in enumerate(rows[:5], 1))
        e.add_field(name="Top Users — 30d", value=fmt(top_users_30, key="user"), inline=False)
        e.add_field(name="Top Users — 365d", value=fmt(top_users_365, key="user"), inline=False)
        e.add_field(name="Top Movies — 30d", value=fmt(top_movies_30, key="title"), inline=False)
        e.add_field(name="Top TV — 30d", value=fmt(top_tv_30, key="title"), inline=False)
        e.set_footer(text=self._now_str())
        return e

    def _build_downloads_embed(self, torrents, status_text: Optional[str]) -> List[discord.Embed]:
        if status_text and torrents is None:
            e = discord.Embed(title="qBittorrent Status", description=status_text, color=0xE67E22)
            e.set_footer(text=self._now_str())
            return [e]
        if not torrents:
            e = discord.Embed(title="qBittorrent Status", description="No downloads in progress.", color=0x00ff00)
            e.set_footer(text=self._now_str())
            return [e]
        embeds: List[discord.Embed] = []
        for t in torrents[:10]:
            progress = t.progress * 100
            speed = t.dlspeed / (1024 * 1024)
            eta_min = t.eta / 60 if t.eta > 0 else 0
            if eta_min < 1:
                eta_text = "<1 min"
            elif eta_min < 60:
                eta_text = f"{int(eta_min)} min"
            else:
                h, m = int(eta_min // 60), int(eta_min % 60)
                eta_text = f"{h}h {m}m" if m else f"{h}h"
            desc = f"**Progress:** {progress:.2f}%\n**Speed:** {speed:.2f} MB/s\n**ETA:** {eta_text}"
            e = discord.Embed(title=t.name, description=desc, color=0x6a0dad)
            e.set_footer(text=self._now_str())
            poster = None
            if self._posters and self.cfg.streams.post_thumbnails:
                cleaned = self._clean_title(t.name)
                if re.search(r"S\d{1,2}E\d{1,2}", t.name, re.I):
                    poster = self._posters.tv_poster(cleaned, None)
                else:
                    poster = self._posters.movie_poster(cleaned, None, None, None)
            if poster:
                e.set_thumbnail(url=poster)
    
            e.set_footer(text=self._now_str())
            embeds.append(e)
        return embeds

    # ---------- Post/edit ----------
    async def _post_or_edit(self, key: str, channel_id: Optional[int], *, embed: Optional[discord.Embed] = None, embeds: Optional[List[discord.Embed]] = None):
        if not channel_id:
            return
        channel = self.client.get_channel(channel_id)
        if channel is None:
            log.error("%s channel not found (%s)", key, channel_id)
            return
        mid = self._msg_ids.get(key)
        try:
            if mid:
                msg = await channel.fetch_message(mid)
                if embed:
                    await msg.edit(embed=embed)
                elif embeds:
                    await msg.edit(embeds=embeds)
            else:
                msg = await (channel.send(embed=embed) if embed else channel.send(embeds=embeds))
                self._msg_ids[key] = msg.id
                save_message_ids(self.cfg.general.message_id_file, self._msg_ids)  # <-- save
        except discord.NotFound:
            msg = await (channel.send(embed=embed) if embed else channel.send(embeds=embeds))
            self._msg_ids[key] = msg.id
            save_message_ids(self.cfg.general.message_id_file, self._msg_ids)      # <-- save
        except Exception:
            log.exception("edit/post failed: %s", key)
