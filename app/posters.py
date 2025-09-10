import requests
from functools import lru_cache

def _params_key(params: dict | None) -> tuple | None:
    if not params:
        return None
    return tuple(sorted((str(k), str(v)) for k, v in params.items()))

class PosterResolver:
    """Resolve public CDN poster URLs via Radarr/Sonarr; safe for Discord embeds."""
    def __init__(self, radarr_url: str, radarr_key: str, sonarr_url: str, sonarr_key: str):
        self.radarr_url = (radarr_url or "").rstrip("/")
        self.radarr_key = radarr_key or ""
        self.sonarr_url = (sonarr_url or "").rstrip("/")
        self.sonarr_key = sonarr_key or ""

    # MOVIES
    def movie_poster(self, title: str | None, year: int | str | None, imdb_id: str | None, tmdb_id: str | int | None) -> str | None:
        if not (self.radarr_url and self.radarr_key):
            return None
        movies = self._radarr_get("/api/v3/movie")
        if movies is not None:
            if imdb_id:
                u = self._radarr_match_key(movies, "imdbId", str(imdb_id))
                if u: return u
            if tmdb_id is not None and str(tmdb_id).isdigit():
                u = self._radarr_match_key(movies, "tmdbId", int(str(tmdb_id)))
                if u: return u
            if title:
                u = self._radarr_match_title_year(movies, title, year)
                if u: return u
        if imdb_id:
            u = self._first_poster(self._radarr_get("/api/v3/movie/lookup", {"imdbId": str(imdb_id)}))
            if u: return u
        if tmdb_id is not None and str(tmdb_id).isdigit():
            u = self._first_poster(self._radarr_get("/api/v3/movie/lookup", {"tmdbId": int(str(tmdb_id))}))
            if u: return u
        if title:
            return self._poster_term_title_year(self._radarr_get("/api/v3/movie/lookup", {"term": title}), title, year)
        return None

    def _radarr_match_key(self, movies, key, value):
        for m in movies or []:
            if str(m.get(key)) == str(value):
                return self._first_poster(m)
        return None

    def _radarr_match_title_year(self, movies, title, year):
        t = (title or "").strip().lower()
        y = str(year) if year is not None else None
        for m in movies or []:
            if str(m.get("title","")).strip().lower() == t and (y is None or str(m.get("year")) == y):
                return self._first_poster(m)
        return None

    # TV
    def tv_poster(self, title: str | None, tvdb_id: str | int | None) -> str | None:
        if not (self.sonarr_url and self.sonarr_key):
            return None
        series = self._sonarr_get("/api/v3/series")
        if series is not None:
            if tvdb_id is not None and str(tvdb_id).isdigit():
                u = self._sonarr_match_key(series, "tvdbId", int(str(tvdb_id)))
                if u: return u
            if title:
                u = self._sonarr_match_title(series, title)
                if u: return u
        if tvdb_id is not None and str(tvdb_id).isdigit():
            u = self._first_poster(self._sonarr_get("/api/v3/series/lookup", {"term": f"tvdb:{int(str(tvdb_id))}"}))
            if u: return u
        if title:
            return self._poster_term_title(self._sonarr_get("/api/v3/series/lookup", {"term": title}), title)
        return None

    def _sonarr_match_key(self, series, key, value):
        for s in series or []:
            if str(s.get(key)) == str(value):
                return self._first_poster(s)
        return None

    def _sonarr_match_title(self, series, title):
        t = (title or "").strip().lower()
        for s in series or []:
            if str(s.get("title","")).strip().lower() == t:
                return self._first_poster(s)
        return None

    # Shared helpers
    def _first_poster(self, item_or_list) -> str | None:
        item = item_or_list
        if isinstance(item_or_list, list):
            if not item_or_list: return None
            item = item_or_list[0]
        imgs = (item or {}).get("images", []) or []
        for im in imgs:
            if im.get("coverType") == "poster" and im.get("remoteUrl"):
                return im["remoteUrl"]
        for im in imgs:
            if im.get("remoteUrl"):
                return im["remoteUrl"]
        return None

    @lru_cache(maxsize=128)
    def _radarr_get_cached(self, path: str, params_key: tuple | None):
        params = dict(params_key) if params_key else {}
        try:
            r = requests.get(f"{self.radarr_url}{path}", headers={"X-Api-Key": self.radarr_key}, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    @lru_cache(maxsize=128)
    def _sonarr_get_cached(self, path: str, params_key: tuple | None):
        params = dict(params_key) if params_key else {}
        try:
            r = requests.get(f"{self.sonarr_url}{path}", headers={"X-Api-Key": self.sonarr_key}, params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    def _radarr_get(self, path: str, params: dict | None = None):
        return self._radarr_get_cached(path, _params_key(params))

    def _sonarr_get(self, path: str, params: dict | None = None):
        return self._sonarr_get_cached(path, _params_key(params))

    def _poster_term_title_year(self, items, title, year):
        if not items: return None
        t = (title or "").strip().lower()
        y = str(year) if year is not None else None
        for it in items:
            if str(it.get("title","")).strip().lower() == t and (y is None or str(it.get("year")) == y):
                return self._first_poster(it)
        return self._first_poster(items)

    def _poster_term_title(self, items, title):
        if not items: return None
        t = (title or "").strip().lower()
        for it in items:
            if str(it.get("title","")).strip().lower() == t:
                return self._first_poster(it)
        return self._first_poster(items)
