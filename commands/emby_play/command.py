"""EmbyPlayCommand: "play <something> on Emby" through this node's speaker (mpv)."""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

for _candidate in ("emby_shared", "lib"):
    _lib_dir: str = str(Path.home() / ".jarvis" / "packages" / "emby_play" / _candidate)
    if _lib_dir not in sys.path:
        sys.path.insert(0, _lib_dir)

try:
    from jarvis_log_client import JarvisLogger
except ImportError:
    import logging

    class JarvisLogger:  # noqa: E303
        def __init__(self, **kw: str) -> None:
            self._log = logging.getLogger(kw.get("service", __name__))

        def error(self, msg: str, **kw: object) -> None: self._log.error(msg)

from jarvis_command_sdk import (
    CommandExample,
    CommandResponse,
    FastPathPattern,
    IJarvisCommand,
    IJarvisSecret,
    JarvisPackage,
    JarvisParameter,
    JarvisSecret,
    JarvisStorage,
    RequestInformation,
)
from jarvis_command_sdk.command import PreRouteResult

from emby_shared.music_common import AUTO, KINDS, PLAYER, ServiceError, fast_arguments, fast_regexes
from emby_shared.emby_service import EmbyService

logger = JarvisLogger(service="emby-play")
_PLAY_ON, _NAME_FIRST = fast_regexes(r"emby")


class EmbyPlayCommand(IJarvisCommand):
    """Voice search and play on Emby."""

    def __init__(self) -> None:
        self._storage = JarvisStorage("emby_play")

    @property
    def command_name(self) -> str:
        return "emby_play"

    @property
    def description(self) -> str:
        return (
            "Play a song, album, artist or playlist from Emby. query is what to play, kind says what it is "
            "(leave empty unless the user says song, album, artist or playlist), artist narrows a song or album. "
            "Use when the user names Emby: 'play ... on Emby'."
        )

    @property
    def associated_service(self) -> Optional[str]:
        return "Emby"

    @property
    def keywords(self) -> List[str]:
        return ["emby", "play on emby", "play from emby", "song", "album", "playlist"]

    @property
    def parameters(self) -> List[JarvisParameter]:
        return [
            JarvisParameter("query", "string", required=True,
                            description="What to play: a song, album, artist or playlist name, without the service"),
            JarvisParameter("kind", "string", required=False, enum_values=KINDS,
                            description="track, album, artist or playlist. Leave empty when unsure."),
            JarvisParameter("artist", "string", required=False,
                            description="The artist, when the user named one for a song or album"),
        ]

    @property
    def fast_path_patterns(self) -> List[FastPathPattern]:
        return [
            FastPathPattern(id="emby.play_on", description="Play something when you say 'on Emby'",
                            example="Play Hysteria by Muse on Emby", regex=_PLAY_ON, handler="_fast_play"),
            FastPathPattern(id="emby.emby_play", description="Play something when the phrase starts with 'Emby'",
                            example="Emby, play Discover Weekly", regex=_NAME_FIRST, handler="_fast_play"),
        ]

    def _fast_play(self, match: "re.Match[str]", voice_command: str) -> Optional[PreRouteResult]:
        args = fast_arguments(match.group("what"))
        return PreRouteResult(arguments=args) if args else None

    @property
    def required_secrets(self) -> List[IJarvisSecret]:
        return [
            JarvisSecret("EMBY_URL", "Address of your Emby server, e.g. http://192.168.1.10:8096", "integration", "string", is_sensitive=False, friendly_name="Server URL"),
            JarvisSecret("EMBY_API_KEY", "An Emby API key (Dashboard, Advanced, API Keys)", "integration", "string", friendly_name="API key"),
            JarvisSecret("EMBY_USER_ID", "User to read playlists as (default: the first user)", "integration", "string", required=False, is_sensitive=False, friendly_name="User ID"),
        ]

    @property
    def required_packages(self) -> List[JarvisPackage]:
        return [JarvisPackage("requests", ">=2.31.0")]

    @property
    def setup_guide(self) -> Optional[str]:
        return (
            '## Connect Emby\n'
            '\n'
            "Plays music from your own Emby server through this node's speaker. Jellyfin's API is the same, so it should work too.\n"
            '\n'
            '1. Enter the server address, for example `http://192.168.1.10:8096`.\n'
            '2. In the Emby dashboard open Advanced, then API Keys, and create a key for Jarvis.\n'
            '3. Optionally enter the user ID whose playlists to read; otherwise the first user is used.\n'
            '4. The node needs `mpv` installed.\n'
        )

    def generate_prompt_examples(self) -> List[CommandExample]:
        return [
            CommandExample("Play Hysteria by Muse on Emby",
                           {"query": "Hysteria", "kind": "track", "artist": "Muse"}, is_primary=True),
            CommandExample("Play the album Black Holes and Revelations on Emby",
                           {"query": "Black Holes and Revelations", "kind": "album"}),
            CommandExample("Play some Muse from Emby", {"query": "Muse", "kind": "artist"}),
        ]

    def generate_adapter_examples(self) -> List[CommandExample]:
        rows = [
            ("Play Bohemian Rhapsody on Emby", "Bohemian Rhapsody", "track", None),
            ("Play Thunderstruck by AC/DC from Emby", "Thunderstruck", "track", "AC/DC"),
            ("Play the album Rumours on Emby", "Rumours", "album", None),
            ("Play Abbey Road by The Beatles on Emby", "Abbey Road", "album", "The Beatles"),
            ("Play Taylor Swift on Emby", "Taylor Swift", "artist", None),
            ("Play my Chill Hits playlist on Emby", "Chill Hits", "playlist", None),
            ("Emby, play Running Up That Hill", "Running Up That Hill", "track", None),
        ]
        out = []
        for text, query, kind, artist in rows:
            params = {"query": query, "kind": kind}
            if artist:
                params["artist"] = artist
            out.append(CommandExample(text, params))
        return out

    def _service(self) -> EmbyService:
        import requests

        url = self._storage.get_secret("EMBY_URL")
        key = self._storage.get_secret("EMBY_API_KEY")
        if not (url and key):
            raise ServiceError("Emby isn't set up yet. Add the server address and API key in the app.")
        return EmbyService(requests, url, key, self._storage.get_secret("EMBY_USER_ID") or "")

    def run(self, request_info: RequestInformation, **kwargs: Any) -> CommandResponse:
        query = str(kwargs.get("query") or "").strip()
        if not query:
            return CommandResponse.error_response(error_details="What would you like me to play?",
                                                  context_data={"error": "missing_query"})
        kind = str(kwargs.get("kind") or AUTO).lower()
        try:
            item = self._service().find(query, kind, kwargs.get("artist"))
            PLAYER.play(item)
        except ServiceError as exc:
            return CommandResponse.error_response(error_details=str(exc), context_data={"error": "service_error"})
        except Exception as exc:  # noqa: BLE001 - never raise into the voice pipeline
            logger.error("Emby play failed", error=str(exc))
            return CommandResponse.error_response(error_details="Emby didn't respond. Try again in a moment.",
                                                  context_data={"error": "unexpected", "detail": str(exc)})
        return CommandResponse.success_response(
            context_data={"message": f"Playing {item.spoken()}.", "kind": item.kind}, wait_for_input=False)
