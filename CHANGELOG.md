# Changelog

## 20261108-1900

- Archived: Jarvis uses Music Assistant as its music integration point. See the note at the top of the README.

## 20261108-1800

- Verified against a live Emby 4.10 server (song, artist, album and playlist).
- Capped a playlist at 50 tracks, because Emby's playlist endpoint ignores `Limit`.

## 20261108-1700

- First draft: "play X on Emby" searches and plays through the node's speaker (mpv).
- Fast paths run "play X on Emby" and "Emby, play X" with no model.
