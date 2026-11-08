"""Find music on an Emby server and turn it into stream URLs for mpv.

Official REST API. The API key travels as the X-Emby-Token header (never in a URL). Jellyfin's API is the same shape.
"""

from __future__ import annotations

from typing import Any, Optional

from emby_shared.music_common import AUTO, KINDS, Resolved, ServiceError, pick

_TIMEOUT = 10
_TYPES = {"MusicArtist": "artist", "MusicAlbum": "album", "Audio": "track", "Playlist": "playlist"}
_TRACK_ORDER = "ParentIndexNumber,IndexNumber,SortName"


class EmbyService:
    def __init__(self, http: Any, base_url: str, api_key: str, user_id: str = "") -> None:
        self._http = http
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._headers = {"X-Emby-Token": api_key, "Accept": "application/json"}
        self._user = user_id.strip()

    def _get(self, path: str, **params: Any) -> dict:
        try:
            r = self._http.get(self._base + path, params=params or None, headers=self._headers, timeout=_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            raise ServiceError("I can't reach your Emby server.") from exc
        if r.status_code in (401, 403):
            raise ServiceError("Emby rejected the API key. Check it in the app.")
        if r.status_code != 200:
            raise ServiceError("Emby didn't answer that. Try again in a moment.")
        return r.json() or {}

    def _user_id(self) -> str:
        if not self._user:  # an API key is not a user, and playlists are read as one
            users = self._get("/Users")
            users = users if isinstance(users, list) else users.get("Items", [])
            if not users:
                raise ServiceError("Emby has no users to read playlists as.")
            self._user = users[0]["Id"]
        return self._user

    def find(self, query: str, kind: str = AUTO, artist: Optional[str] = None) -> Resolved:
        kind = kind if kind in KINDS else AUTO
        items = self._get("/Items", SearchTerm=query, IncludeItemTypes="Audio,MusicAlbum,MusicArtist,Playlist",
                          Recursive="true", Limit=30, Fields="AlbumArtist,Artists").get("Items") or []
        found: dict[str, list] = {}
        for it in items:
            k = _TYPES.get(it.get("Type", ""))
            if k and not (k == "playlist" and it.get("MediaType") not in (None, "Audio")):  # not a video playlist
                found.setdefault(k, []).append({**it, "name": it.get("Name", "")})
        if artist:
            for k in ("track", "album"):
                found[k] = sorted(found.get(k, []), key=lambda m: artist.casefold() not in _by(m).casefold())
        hit = pick(found, query, kind)
        if hit is None:
            raise ServiceError(f"I couldn't find {query} on Emby.")
        k, item = hit
        ids = self._track_ids(k, item)
        if not ids:
            raise ServiceError(f"{item['name']} has nothing playable on Emby.")
        urls = [f"{self._base}/Audio/{i}/stream?static=true" for i in ids]
        return Resolved(k, item["name"], _by(item) if k != "playlist" else "", urls,
                        headers={"X-Emby-Token": self._key}, shuffle=k == "artist")

    def _track_ids(self, kind: str, item: dict) -> list[str]:
        base = {"IncludeItemTypes": "Audio", "Recursive": "true", "Limit": 50}
        if kind == "track":
            return [item["Id"]]
        if kind == "album":
            rows = self._get("/Items", ParentId=item["Id"], SortBy=_TRACK_ORDER, **base).get("Items")
        elif kind == "artist":
            rows = self._get("/Items", ArtistIds=item["Id"], SortBy="Random", **base).get("Items")
        else:
            rows = self._get(f"/Playlists/{item['Id']}/Items", UserId=self._user_id()).get("Items")
        return [r["Id"] for r in rows or [] if r.get("Id")]


def _by(item: dict) -> str:
    return item.get("AlbumArtist") or ", ".join(item.get("Artists") or [])
