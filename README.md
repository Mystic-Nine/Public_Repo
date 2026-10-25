# Telegram Leech Bot (Telegram → Telegram only)

Cleaned build of KPSML-X for **Heroku / Render / Railway**.

Everything those platforms forbid has been removed: **Mirror (GDrive / RClone / DDL), Torrent (qBittorrent / aria2),
RSS, Mega, Clone, GDrive tools (list / count / delete / clean), torrent search, yt-dlp, direct-link generators, web file-selector**.

What is left: reply to a Telegram file (or a `t.me` link) with `/leech` and the bot re-uploads it to Telegram
(rename, zip / unzip, split, thumbnails, screenshots, mediainfo, dump chats, auto-rename, user settings, IMDB / AniList / MDL / poster, ...).

## Deploy
1. Fill the variables from `config.env` as environment variables of your service
   (BOT_TOKEN, OWNER_ID, TELEGRAM_API, TELEGRAM_HASH, DATABASE_URL, ... ).
2. **Heroku**: `heroku stack:set container` and push (`heroku.yml` is included).
   **Render / Railway**: create a *Docker* web service from this repo (uses `Dockerfile`).
3. Leave `UPSTREAM_REPO` empty. If you set it, the bot pulls that repo on every start and replaces this code.
4. Optional: set `BASE_URL` to your service URL to keep a free instance awake.

The container listens on `$PORT` (health check at `/`), which all three platforms require.
