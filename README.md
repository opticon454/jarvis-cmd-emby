# jarvis-cmd-emby

A [Jarvis](https://github.com/alexberardi/jarvis-server) Pantry package that plays music from your own Emby server through the node's speaker.

## What you can say

| You say                               | Plays                                |
| ------------------------------------- | ------------------------------------ |
| "Play Hysteria by Muse on Emby"       | The song                             |
| "Play the album Rumours from Emby"    | The album                            |
| "Play Taylor Swift on Emby"           | The artist (an exact name), shuffled |
| "Play my Chill Hits playlist on Emby" | The playlist                         |
| "Emby, play Discover Weekly"          | Best match                           |

The phrase must include "Emby". These are fast paths, so the node runs them with no model, and each can be switched off
in the app's Inspect fast-paths screen. With [jarvis-cmd-music](https://github.com/opticon454/jarvis-cmd-music), "play
Korn" also works and uses your default music service.

## Requirements

- An Emby server with a music library. Jellyfin uses the same API and should work.
- `mpv` on the node.

## Settings

Entered in the Jarvis app; nothing is stored in this repository.

| Setting        | Required | Meaning                                                          |
| -------------- | -------- | ---------------------------------------------------------------- |
| `EMBY_URL`     | Yes      | Server address, e.g. `http://192.168.1.10:8096`.                 |
| `EMBY_API_KEY` | Yes      | An API key from Dashboard, Advanced, API Keys. Sent as a header. |
| `EMBY_USER_ID` | No       | User to read playlists as. Default: the first user.              |

## How it plays

The command finds the music, then starts `mpv` on the node with the stream addresses. A new play replaces the old one,
pauses the Spotify Connect receiver if it is running, and ends any other `mpv`, so two streams never share the speaker.
Audio goes to a connected Bluetooth speaker, else PulseAudio (so the agent can lower it while you talk), else the Pi
image's ALSA `output` alias. Long queues are limited to 50 tracks.

## Status

Verified live on 20261108 against an Emby 4.10 server with a real music library: a song by artist, an exact artist name
(beating a song of the same name), an album in track order, and a playlist; the stream addresses return audio, and mpv
opens them with the API key sent as a header. **Not yet heard through a node speaker.** Jellyfin is untested.

## Tests

```bash
PYTHONPATH=/path/to/jarvis-command-sdk python3 -m pytest
```

The tests use fakes, so no node, account or network is needed.

## Licence

Apache-2.0. Not affiliated with Emby. `mpv` is a separate program and is not included.
