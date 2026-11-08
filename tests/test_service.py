import pytest

from emby_shared.music_common import ServiceError
from emby_shared.emby_service import EmbyService


class Resp:
    def __init__(self, payload, status=200):
        self.status_code, self._p = status, payload

    def json(self):
        return self._p


class Http:
    def __init__(self, routes, status=200):
        self.routes, self.status, self.calls = routes, status, []

    def get(self, url, params=None, headers=None, timeout=None):
        path = url.split("http://emby:8096")[1]
        self.calls.append((path, params or {}, headers))
        if self.status != 200:
            return Resp({}, self.status)
        route = self.routes[path]
        return Resp(route(params) if callable(route) else route)


def items(*rows):
    return {"Items": list(rows)}


def svc(routes, **kw):
    http = Http(routes, **kw)
    return EmbyService(http, "http://emby:8096/", "KEY", kw.pop("user", "") or "U1"), http


SONG = {"Id": "a1", "Name": "Hysteria", "Type": "Audio", "AlbumArtist": "Muse"}
OTHER = {"Id": "a2", "Name": "Hysteria", "Type": "Audio", "Artists": ["Def Leppard"]}


def test_track_prefers_the_named_artist_and_streams_statically_with_the_key_in_a_header():
    s, http = svc({"/Items": items(OTHER, SONG)})
    r = s.find("Hysteria", "track", "Muse")
    assert r.urls == ["http://emby:8096/Audio/a1/stream?static=true"] and r.spoken() == "Hysteria by Muse"
    assert r.headers == {"X-Emby-Token": "KEY"} and "KEY" not in r.urls[0]
    assert http.calls[0][1]["SearchTerm"] == "Hysteria" and "Audio" in http.calls[0][1]["IncludeItemTypes"]


def test_exact_artist_wins_and_expands_to_their_songs_shuffled():
    def route(p):
        return items({"Id": "r1", "Name": "Muse", "Type": "MusicArtist"}, SONG) if "SearchTerm" in p else items({"Id": "a1"}, {"Id": "a3"})
    r = svc({"/Items": route})[0].find("muse")
    assert r.kind == "artist" and r.shuffle and len(r.urls) == 2


def test_album_is_read_in_track_order_and_playlist_as_the_user():
    def route(p):
        if "SearchTerm" in p:
            return items({"Id": "al", "Name": "Absolution", "Type": "MusicAlbum", "AlbumArtist": "Muse"},
                         {"Id": "pl", "Name": "Mix", "Type": "Playlist"})
        assert p["ParentId"] == "al" and p["SortBy"].startswith("ParentIndexNumber,IndexNumber")
        return items({"Id": "t1"}, {"Id": "t2"})

    routes = {"/Items": route, "/Playlists/pl/Items": lambda p: items({"Id": "p1"})}
    s, http = svc(routes)
    assert [u.split("/")[4] for u in s.find("Absolution", "album").urls] == ["t1", "t2"]
    assert s.find("Mix", "playlist").urls[0].split("/")[4] == "p1" and http.calls[-1][1]["UserId"] == "U1"


def test_a_video_playlist_is_not_music():
    routes = {"/Items": items({"Id": "v", "Name": "Movies", "Type": "Playlist", "MediaType": "Video"})}
    with pytest.raises(ServiceError, match="couldn't find Movies on Emby"):
        svc(routes)[0].find("Movies")


def test_without_a_user_id_the_first_user_is_used():
    routes = {"/Items": items({"Id": "pl", "Name": "Mix", "Type": "Playlist"}), "/Users": [{"Id": "first"}],
              "/Playlists/pl/Items": items({"Id": "p1"})}
    http = Http(routes)
    EmbyService(http, "http://emby:8096", "K").find("Mix", "playlist")
    assert http.calls[-1][1]["UserId"] == "first"


@pytest.mark.parametrize("status,text", [(401, "rejected the API key"), (403, "rejected"), (500, "didn't answer")])
def test_failures_are_speakable(status, text):
    with pytest.raises(ServiceError, match=text):
        svc({}, status=status)[0].find("x")


def test_nothing_found_and_unreachable():
    with pytest.raises(ServiceError, match="couldn't find Nope on Emby"):
        svc({"/Items": items()})[0].find("Nope")

    class Down:
        def get(self, *a, **k):
            raise OSError("refused")

    with pytest.raises(ServiceError, match="can't reach your Emby"):
        EmbyService(Down(), "http://emby:8096", "K").find("x")
