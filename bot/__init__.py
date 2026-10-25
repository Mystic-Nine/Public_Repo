#!/usr/bin/env python3
from tzlocal import get_localzone
from pytz import timezone
from datetime import datetime
from inspect import signature
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pyrogram import Client as tgClient, enums, utils as pyroutils
from pymongo import MongoClient
from asyncio import Lock, get_event_loop, new_event_loop, set_event_loop, iscoroutine, isfuture
from dotenv import load_dotenv, dotenv_values
from threading import Thread
from time import sleep, time
from subprocess import Popen
from os import path as ospath, environ
from faulthandler import enable as faulthandler_enable
from socket import setdefaulttimeout
from logging import getLogger, Formatter, FileHandler, StreamHandler, INFO, ERROR, basicConfig, error as log_error, info as log_info, warning as log_warning
from logging import WARNING, getLevelName
from logging.handlers import RotatingFileHandler
from functools import wraps
from inspect import iscoroutinefunction
from uvloop import install

faulthandler_enable()
install()
setdefaulttimeout(600)

pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999

botStartTime = time()

# Less logging = faster bot + small log.txt (so /log always works).
# LOG_LEVEL env: DEBUG / INFO / WARNING (default) / ERROR
_lvl = getLevelName(environ.get('LOG_LEVEL', 'WARNING').strip().upper())
_lvl = _lvl if isinstance(_lvl, int) else WARNING

# Records go to a queue; a background thread writes file/console. A slow disk (os.stat in
# RotatingFileHandler blocked the loop 4s on Heroku) can no longer freeze the bot.
from logging.handlers import QueueHandler, QueueListener
from queue import SimpleQueue
_log_fmt = Formatter("[%(asctime)s] [%(levelname)s] - %(message)s", datefmt="%d-%b-%y %I:%M:%S %p")
_file_h = RotatingFileHandler('log.txt', maxBytes=2 * 1024 * 1024, backupCount=1, encoding='utf-8')
_con_h = StreamHandler()
for _h in (_file_h, _con_h):
    _h.setFormatter(_log_fmt)
_log_q = SimpleQueue()
_log_listener = QueueListener(_log_q, _file_h, _con_h, respect_handler_level=True)
_log_listener.start()
_qh = QueueHandler(_log_q)
_qh.setFormatter(Formatter('%(message)s'))   # real format is applied once, by the listener's handlers
basicConfig(handlers=[_qh], level=_lvl)

try:
    from bot.helper.telegram_helper.button_style import install as _install_button_colors
    _install_button_colors()
except Exception as _e:
    log_warning(f"button colors not installed: {_e!r}")

for _noisy in ("pyrogram", "aiohttp", "httpx", "urllib3", "apscheduler", "pymongo", "asyncio", "PIL"):
    getLogger(_noisy).setLevel(ERROR)

LOGGER = getLogger(__name__)

load_dotenv('config.env', override=True)

Interval = []
GLOBAL_EXTENSION_FILTER = []
user_data = {}
extra_buttons = {}
queued_dl = {}
queued_up = {}
bot_cache = {}
non_queued_dl = set()
non_queued_up = set()


download_dict_lock = Lock()
status_reply_dict_lock = Lock()
queue_dict_lock = Lock()
status_reply_dict = {}
download_dict = {}

BOT_TOKEN = environ.get('BOT_TOKEN', '')
if len(BOT_TOKEN) == 0:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

bot_id = BOT_TOKEN.split(':', 1)[0]

DATABASE_URL = environ.get('DATABASE_URL', '')
if len(DATABASE_URL) == 0:
    DATABASE_URL = ''

if DATABASE_URL:
    conn = MongoClient(DATABASE_URL)
    db = conn.kpsmlx
    current_config = dict(dotenv_values('config.env'))
    old_config = db.settings.deployConfig.find_one({'_id': bot_id})
    if old_config is None:
        db.settings.deployConfig.replace_one(
            {'_id': bot_id}, current_config, upsert=True)
    else:
        del old_config['_id']
    if old_config and old_config != current_config:
        db.settings.deployConfig.replace_one(
            {'_id': bot_id}, current_config, upsert=True)
    elif config_dict := db.settings.config.find_one({'_id': bot_id}):
        del config_dict['_id']
        for key, value in config_dict.items():
            environ[key] = str(value)
    if pf_dict := db.settings.files.find_one({'_id': bot_id}):
        del pf_dict['_id']
        for key, value in pf_dict.items():
            if value:
                file_ = key.replace('__', '.')
                with open(file_, 'wb+') as f:
                    f.write(value)
    conn.close()
    BOT_TOKEN = environ.get('BOT_TOKEN', '')
    bot_id = BOT_TOKEN.split(':', 1)[0]
    DATABASE_URL = environ.get('DATABASE_URL', '')
else:
    config_dict = {}

OWNER_ID = environ.get('OWNER_ID', '')
if len(OWNER_ID) == 0:
    log_error("OWNER_ID variable is missing! Exiting now")
    exit(1)
else:
    OWNER_ID = int(OWNER_ID)

TELEGRAM_API = environ.get('TELEGRAM_API', '')
if len(TELEGRAM_API) == 0:
    log_error("TELEGRAM_API variable is missing! Exiting now")
    exit(1)
else:
    TELEGRAM_API = int(TELEGRAM_API)

TELEGRAM_HASH = environ.get('TELEGRAM_HASH', '')
if len(TELEGRAM_HASH) == 0:
    log_error("TELEGRAM_HASH variable is missing! Exiting now")
    exit(1)
    
TIMEZONE = environ.get('TIMEZONE', '')
if len(TIMEZONE) == 0:
    TIMEZONE = 'Asia/Kolkata'
    
def changetz(*args):
    return datetime.now(timezone(TIMEZONE)).timetuple()
Formatter.converter = changetz
log_info("TIMEZONE synced with logging status")

DOWNLOAD_DIR = environ.get('DOWNLOAD_DIR', '')
if len(DOWNLOAD_DIR) == 0:
    DOWNLOAD_DIR = '/usr/src/app/downloads/'
elif not DOWNLOAD_DIR.endswith("/"):
    DOWNLOAD_DIR = f'{DOWNLOAD_DIR}/'

AUTHORIZED_CHATS = environ.get('AUTHORIZED_CHATS', '')
if AUTHORIZED_CHATS:
    aid = AUTHORIZED_CHATS.split()
    for id_ in aid:
        chat_id, *topic_ids = id_.split(':')
        chat_id = int(chat_id)
        user_data.setdefault(chat_id, {'is_auth': True})
        if topic_ids:
            user_data[chat_id].setdefault('topic_ids', []).extend(map(int, topic_ids))

SUDO_USERS = environ.get('SUDO_USERS', '')
if len(SUDO_USERS) != 0:
    aid = SUDO_USERS.split()
    for id_ in aid:
        user_data[int(id_.strip())] = {'is_sudo': True}
        
BLACKLIST_USERS = environ.get('BLACKLIST_USERS', '')
if len(BLACKLIST_USERS) != 0:
    for id_ in BLACKLIST_USERS.split():
        user_data[int(id_.strip())] = {'is_blacklist': True}

EXTENSION_FILTER = environ.get('EXTENSION_FILTER', '')
if len(EXTENSION_FILTER) > 0:
    fx = EXTENSION_FILTER.split()
    for x in fx:
        x = x.lstrip('.')
        GLOBAL_EXTENSION_FILTER.append(x.strip().lower())

LINKS_LOG_ID = environ.get('LINKS_LOG_ID', '')
LINKS_LOG_ID = '' if len(LINKS_LOG_ID) == 0 else int(LINKS_LOG_ID)

LEECH_LOG_ID = environ.get('LEECH_LOG_ID', '')
if len(LEECH_LOG_ID) == 0:
    LEECH_LOG_ID = ''

EXCEP_CHATS = environ.get('EXCEP_CHATS', '')
if len(EXCEP_CHATS) == 0:
    EXCEP_CHATS = ''

def wztgClient(*args, **kwargs):
    if 'max_concurrent_transmissions' in signature(tgClient.__init__).parameters:
        # Max files uploading/downloading at the same time (Pyrogram docs: "too high may
        # result in network related issues"). 1000 = unlimited -> a dozen parallel uploads
        # saturate the single event-loop thread, pings time out and every session dies
        # ("Session is stopped"). 4 was too slow. 16 is the middle; override with MAX_TRANSMISSIONS.
        kwargs['max_concurrent_transmissions'] = int(environ.get('MAX_TRANSMISSIONS', '16') or 16)
    # No sqlite session file (same as the wzgram authors' WZML-X): nothing to corrupt on restart,
    # no disk writes for every update. A bot token logs in again in a second.
    if 'in_memory' in signature(tgClient.__init__).parameters:
        kwargs['in_memory'] = True
    return tgClient(*args, **kwargs)

# --- pyrofork / wzgram compat: loop + start() ---
# pyrofork  : Client.start() is sync (auto-wrapped) and client.loop exists
# wzgram    : Client.start() is a coroutine, client.loop may not exist
try:
    bot_loop = get_event_loop()
except RuntimeError:
    bot_loop = new_event_loop()
    set_event_loop(bot_loop)

def tg_start(client):
    res = client.start()
    if iscoroutine(res) or isfuture(res):
        res = bot_loop.run_until_complete(res)
    return res if res is not None else client

# --- Add this block to ensure an event loop exists ---
# try:
#     loop = get_event_loop()
# except RuntimeError:
#     loop = new_event_loop()
#     set_event_loop(loop)

IS_PREMIUM_USER = False
user = ''
USER_SESSION_STRING = environ.get('USER_SESSION_STRING', '')
if len(USER_SESSION_STRING) != 0:
    log_info("Creating client from USER_SESSION_STRING")
    try:
        user = wztgClient('user', TELEGRAM_API, TELEGRAM_HASH, session_string=USER_SESSION_STRING, sleep_threshold=60,
                        parse_mode=enums.ParseMode.HTML, no_updates=True)
        user = tg_start(user)
        IS_PREMIUM_USER = user.me.is_premium
    except Exception as e:
        log_error(f"Failed making client from USER_SESSION_STRING : {e}")
        user = ''

METADATA = environ.get('METADATA', '')
if len(METADATA) == 0:
    METADATA = ''

ATTACHMENT = environ.get('ATTACHMENT', '')
if len(ATTACHMENT) == 0:
    ATTACHMENT = ''

CAP_FONT = environ.get('CAP_FONT', '').lower()
if CAP_FONT.strip() not in ['', 'b', 'i', 'u', 's', 'spoiler', 'code']:
    CAP_FONT = 'b'

LEECH_FILENAME_PREFIX = environ.get('LEECH_FILENAME_PREFIX', '')
if len(LEECH_FILENAME_PREFIX) == 0:
    LEECH_FILENAME_PREFIX = ''

LEECH_FILENAME_SUFFIX = environ.get('LEECH_FILENAME_SUFFIX', '')
if len(LEECH_FILENAME_SUFFIX) == 0:
    LEECH_FILENAME_SUFFIX = ''

LEECH_FILENAME_CAPTION = environ.get('LEECH_FILENAME_CAPTION', '')
if len(LEECH_FILENAME_CAPTION) == 0:
    LEECH_FILENAME_CAPTION = ''

LEECH_FILENAME_REMNAME = environ.get('LEECH_FILENAME_REMNAME', '')
if len(LEECH_FILENAME_REMNAME) == 0:
    LEECH_FILENAME_REMNAME = ''
    
MAX_SPLIT_SIZE = 4194304000 if IS_PREMIUM_USER else 2097152000

LEECH_SPLIT_SIZE = environ.get('LEECH_SPLIT_SIZE', '')
if str(LEECH_SPLIT_SIZE) in ["4194304000", "2097152000"] or len(LEECH_SPLIT_SIZE) == 0 or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE:
    LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
else:
    LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

BOT_MAX_TASKS = environ.get('BOT_MAX_TASKS', '')
BOT_MAX_TASKS = int(BOT_MAX_TASKS) if BOT_MAX_TASKS.isdigit() else ''

STATUS_UPDATE_INTERVAL = environ.get('STATUS_UPDATE_INTERVAL', '')
if len(STATUS_UPDATE_INTERVAL) == 0:
    STATUS_UPDATE_INTERVAL = 5  # 2s default made every task edit Telegram constantly (flood + loop load)
else:
    STATUS_UPDATE_INTERVAL = int(STATUS_UPDATE_INTERVAL)

AUTO_DELETE_MESSAGE_DURATION = environ.get('AUTO_DELETE_MESSAGE_DURATION', '')
if len(AUTO_DELETE_MESSAGE_DURATION) == 0:
    AUTO_DELETE_MESSAGE_DURATION = 30
else:
    AUTO_DELETE_MESSAGE_DURATION = int(AUTO_DELETE_MESSAGE_DURATION)

STATUS_LIMIT = environ.get('STATUS_LIMIT', '')
STATUS_LIMIT = 4 if len(STATUS_LIMIT) == 0 else int(STATUS_LIMIT)

CMD_SUFFIX = environ.get('CMD_SUFFIX', '')

QUEUE_ALL = environ.get('QUEUE_ALL', '')
QUEUE_ALL = '' if len(QUEUE_ALL) == 0 else int(QUEUE_ALL)

QUEUE_DOWNLOAD = environ.get('QUEUE_DOWNLOAD', '')
QUEUE_DOWNLOAD = '' if len(QUEUE_DOWNLOAD) == 0 else int(QUEUE_DOWNLOAD)

QUEUE_UPLOAD = environ.get('QUEUE_UPLOAD', '')
QUEUE_UPLOAD = '' if len(QUEUE_UPLOAD) == 0 else int(QUEUE_UPLOAD)

INCOMPLETE_TASK_NOTIFIER = environ.get('INCOMPLETE_TASK_NOTIFIER', '')
INCOMPLETE_TASK_NOTIFIER = INCOMPLETE_TASK_NOTIFIER.lower() == 'true'

AS_DOCUMENT = environ.get('AS_DOCUMENT', 'true')
AS_DOCUMENT = AS_DOCUMENT.lower() == 'true'

SHOW_MEDIAINFO = environ.get('SHOW_MEDIAINFO', '')
SHOW_MEDIAINFO = SHOW_MEDIAINFO.lower() == 'true'

SCREENSHOTS_MODE = environ.get('SCREENSHOTS_MODE', '')
SCREENSHOTS_MODE = SCREENSHOTS_MODE.lower() == 'true'

SOURCE_LINK = environ.get('SOURCE_LINK', '')
SOURCE_LINK = SOURCE_LINK.lower() == 'true'

DELETE_LINKS = environ.get('DELETE_LINKS', '')
DELETE_LINKS = DELETE_LINKS.lower() == 'true'

EQUAL_SPLITS = environ.get('EQUAL_SPLITS', '')
EQUAL_SPLITS = EQUAL_SPLITS.lower() == 'true'

MEDIA_GROUP = environ.get('MEDIA_GROUP', '')
MEDIA_GROUP = MEDIA_GROUP.lower() == 'true'

BASE_URL = environ.get('BASE_URL', '').rstrip("/")
if len(BASE_URL) == 0:
    log_warning('BASE_URL not provided!')
    BASE_URL = ''

UPSTREAM_REPO = environ.get('UPSTREAM_REPO', '')
if len(UPSTREAM_REPO) == 0:
    UPSTREAM_REPO = ''

UPSTREAM_BRANCH = environ.get('UPSTREAM_BRANCH', '')
if len(UPSTREAM_BRANCH) == 0:
    UPSTREAM_BRANCH = 'kpsmlx'
    
UPGRADE_PACKAGES = environ.get('UPGRADE_PACKAGES', '')
UPGRADE_PACKAGES = UPGRADE_PACKAGES.lower() == 'true'

STORAGE_THRESHOLD = environ.get('STORAGE_THRESHOLD', '')
STORAGE_THRESHOLD = '' if len(STORAGE_THRESHOLD) == 0 else float(STORAGE_THRESHOLD)

LEECH_LIMIT = environ.get('LEECH_LIMIT', '')
LEECH_LIMIT = '' if len(LEECH_LIMIT) == 0 else float(LEECH_LIMIT)

USER_MAX_TASKS = environ.get('USER_MAX_TASKS', '')
USER_MAX_TASKS = int(USER_MAX_TASKS) if USER_MAX_TASKS.isdigit() else ''

USER_TIME_INTERVAL = environ.get('USER_TIME_INTERVAL', '')
USER_TIME_INTERVAL = int(USER_TIME_INTERVAL) if USER_TIME_INTERVAL.isdigit() else 0

FSUB_IDS = environ.get('FSUB_IDS', '')
if len(FSUB_IDS) == 0:
    FSUB_IDS = ''
    
LINKS_LOG_ID = environ.get('LINKS_LOG_ID', '')
LINKS_LOG_ID = '' if len(LINKS_LOG_ID) == 0 else int(LINKS_LOG_ID)

BOT_PM = environ.get('BOT_PM', 'true')
BOT_PM = BOT_PM.lower() == 'true'

DAILY_TASK_LIMIT = environ.get('DAILY_TASK_LIMIT', '')
DAILY_TASK_LIMIT = '' if len(DAILY_TASK_LIMIT) == 0 else int(DAILY_TASK_LIMIT)

DAILY_LEECH_LIMIT = environ.get('DAILY_LEECH_LIMIT', '')
DAILY_LEECH_LIMIT = '' if len(
    DAILY_LEECH_LIMIT) == 0 else float(DAILY_LEECH_LIMIT)

BOT_THEME = environ.get('BOT_THEME', '')
if len(BOT_THEME) == 0:
    BOT_THEME = 'minimal'

IMAGES = environ.get('IMAGES', '')
IMAGES = (IMAGES.replace("'", '').replace('"', '').replace(
    '[', '').replace(']', '').replace(",", "")).split()
if IMAGES:
    STATUS_LIMIT = 2

IMG_SEARCH = environ.get('IMG_SEARCH', '')
IMG_SEARCH = (IMG_SEARCH.replace("'", '').replace('"', '').replace(
    '[', '').replace(']', '').replace(",", "")).split()

IMG_PAGE = environ.get('IMG_PAGE', '')
IMG_PAGE = int(IMG_PAGE) if IMG_PAGE.isdigit() else ''

AUTHOR_NAME = environ.get('AUTHOR_NAME', '')
if len(AUTHOR_NAME) == 0:
    AUTHOR_NAME = 'ʀᴀʀᴇ ʙᴏᴛꜱ ʜᴜʙ'

AUTHOR_URL = environ.get('AUTHOR_URL', '')
if len(AUTHOR_URL) == 0:
    AUTHOR_URL = 'https://telegram.me/Rare_Bots_Hub'

TITLE_NAME = environ.get('TITLE_NAME', '')
if len(TITLE_NAME) == 0:
    TITLE_NAME = 'Rare Leech Bot'
    
COVER_IMAGE = environ.get('COVER_IMAGE', '')
if len(COVER_IMAGE) == 0:
    COVER_IMAGE = 'https://graph.org/file/b4f436c65b5a4a64167c6-fc565d1449028a72dc.jpg'

SAVE_MSG = environ.get('SAVE_MSG', '')
SAVE_MSG = SAVE_MSG.lower() == 'true'


SAFE_MODE = environ.get('SAFE_MODE', '')
SAFE_MODE = SAFE_MODE.lower() == 'true'

SET_COMMANDS = environ.get('SET_COMMANDS', 'true')
SET_COMMANDS = SET_COMMANDS.lower() == 'true'

CLEAN_LOG_MSG = environ.get('CLEAN_LOG_MSG', '')
CLEAN_LOG_MSG = CLEAN_LOG_MSG.lower() == 'true'
    
SHOW_EXTRA_CMDS = environ.get('SHOW_EXTRA_CMDS', 'true')
SHOW_EXTRA_CMDS = SHOW_EXTRA_CMDS.lower() == 'true'

TOKEN_TIMEOUT = environ.get('TOKEN_TIMEOUT', '')
TOKEN_TIMEOUT = int(TOKEN_TIMEOUT) if TOKEN_TIMEOUT.isdigit() else ''

LOGIN_PASS = environ.get('LOGIN_PASS', '')
if len(LOGIN_PASS) == 0:
    LOGIN_PASS = None

TMDB_API_KEY = environ.get('TMDB_API_KEY', '')
if len(TMDB_API_KEY) == 0:
    TMDB_API_KEY = ''

IMDB_TEMPLATE = environ.get('IMDB_TEMPLATE', '')
if len(IMDB_TEMPLATE) == 0:
    IMDB_TEMPLATE = '''<b>Title: </b> {title} [{year}]
<b>Also Known As:</b> {aka}
<b>Rating ⭐️:</b> <i>{rating}</i>
<b>Release Info: </b> <a href="{url_releaseinfo}">{release_date}</a>
<b>Genre: </b>{genres}
<b>IMDb URL:</b> {url}
<b>Language: </b>{languages}
<b>Country of Origin : </b> {countries}

<b>Story Line: </b><code>{plot}</code>

<a href="{url_cast}">Read More ...</a>'''

ANIME_TEMPLATE = environ.get('ANIME_TEMPLATE', '')
if len(ANIME_TEMPLATE) == 0:
    ANIME_TEMPLATE = '''<b>{ro_title}</b>({na_title})
<b>Format</b>: <code>{format}</code>
<b>Status</b>: <code>{status}</code>
<b>Start Date</b>: <code>{startdate}</code>
<b>End Date</b>: <code>{enddate}</code>
<b>Season</b>: <code>{season}</code>
<b>Country</b>: {country}
<b>Episodes</b>: <code>{episodes}</code>
<b>Duration</b>: <code>{duration}</code>
<b>Average Score</b>: <code>{avgscore}</code>
<b>Genres</b>: {genres}
<b>Hashtag</b>: {hashtag}
<b>Studios</b>: {studios}

<b>Description</b>: <i>{description}</i>'''

MDL_TEMPLATE = environ.get('MDL_TEMPLATE', '')
if len(MDL_TEMPLATE) == 0:
    MDL_TEMPLATE = '''<b>Title:</b> {title}
<b>Also Known As:</b> {aka}
<b>Rating ⭐️:</b> <i>{rating}</i>
<b>Release Info:</b> {aired_date}
<b>Genre:</b> {genres}
<b>MyDramaList URL:</b> {url}
<b>Language:</b> #Korean
<b>Country of Origin:</b> {country}

<b>Story Line:</b> {synopsis}

<a href='{url}'>Read More ...</a>'''

config_dict = {'ANIME_TEMPLATE': ANIME_TEMPLATE,
               'AS_DOCUMENT': AS_DOCUMENT,
               'AUTHORIZED_CHATS': AUTHORIZED_CHATS,
               'AUTO_DELETE_MESSAGE_DURATION': AUTO_DELETE_MESSAGE_DURATION,
               'BASE_URL': BASE_URL,
               'BLACKLIST_USERS': BLACKLIST_USERS,
               'BOT_TOKEN': BOT_TOKEN,
               'BOT_MAX_TASKS': BOT_MAX_TASKS,
               'CAP_FONT': CAP_FONT,
               'CMD_SUFFIX': CMD_SUFFIX,
               'DATABASE_URL': DATABASE_URL,
               'METADATA': METADATA,
               'ATTACHMENT': ATTACHMENT,
               'TMDB_API_KEY': TMDB_API_KEY,
               'DELETE_LINKS': DELETE_LINKS,
               'DOWNLOAD_DIR': DOWNLOAD_DIR,
               'STORAGE_THRESHOLD': STORAGE_THRESHOLD,
               'LEECH_LIMIT': LEECH_LIMIT,
               'FSUB_IDS': FSUB_IDS,
               'USER_MAX_TASKS': USER_MAX_TASKS,
               'USER_TIME_INTERVAL': USER_TIME_INTERVAL,
               'DAILY_TASK_LIMIT': DAILY_TASK_LIMIT,
               'DAILY_LEECH_LIMIT': DAILY_LEECH_LIMIT,
               'LEECH_LOG_ID': LEECH_LOG_ID,
               'LINKS_LOG_ID': LINKS_LOG_ID,
               'EXCEP_CHATS': EXCEP_CHATS,
               'BOT_PM': BOT_PM,
               'BOT_THEME': BOT_THEME,
               'IMAGES': IMAGES,
               'IMG_SEARCH': IMG_SEARCH,
               'IMG_PAGE': IMG_PAGE,
               'IMDB_TEMPLATE': IMDB_TEMPLATE,
               'AUTHOR_NAME': AUTHOR_NAME,
               'AUTHOR_URL': AUTHOR_URL,
               'COVER_IMAGE': COVER_IMAGE,
               'TITLE_NAME': TITLE_NAME,
               'TIMEZONE': TIMEZONE,
               'EQUAL_SPLITS': EQUAL_SPLITS,
               'EXTENSION_FILTER': EXTENSION_FILTER,
               'INCOMPLETE_TASK_NOTIFIER': INCOMPLETE_TASK_NOTIFIER,
               'LEECH_FILENAME_PREFIX': LEECH_FILENAME_PREFIX,
               'LEECH_FILENAME_SUFFIX': LEECH_FILENAME_SUFFIX,
               'LEECH_FILENAME_CAPTION': LEECH_FILENAME_CAPTION,
               'LEECH_FILENAME_REMNAME': LEECH_FILENAME_REMNAME,
               'LEECH_SPLIT_SIZE': LEECH_SPLIT_SIZE,
               'LOGIN_PASS': LOGIN_PASS,
               'TOKEN_TIMEOUT': TOKEN_TIMEOUT,
               'MDL_TEMPLATE': MDL_TEMPLATE,
               'MEDIA_GROUP': MEDIA_GROUP,
               'OWNER_ID': OWNER_ID,
               'QUEUE_ALL': QUEUE_ALL,
               'QUEUE_DOWNLOAD': QUEUE_DOWNLOAD,
               'QUEUE_UPLOAD': QUEUE_UPLOAD,
               'SAVE_MSG': SAVE_MSG,
               'SAFE_MODE': SAFE_MODE,
               'SET_COMMANDS': SET_COMMANDS,
               'SHOW_MEDIAINFO': SHOW_MEDIAINFO,
               'SCREENSHOTS_MODE': SCREENSHOTS_MODE,
               'CLEAN_LOG_MSG': CLEAN_LOG_MSG,
               'SHOW_EXTRA_CMDS': SHOW_EXTRA_CMDS,
               'SOURCE_LINK': SOURCE_LINK,
               'STATUS_LIMIT': STATUS_LIMIT,
               'STATUS_UPDATE_INTERVAL': STATUS_UPDATE_INTERVAL,
               'SUDO_USERS': SUDO_USERS,
               'TELEGRAM_API': TELEGRAM_API,
               'TELEGRAM_HASH': TELEGRAM_HASH,
               'UPSTREAM_REPO': UPSTREAM_REPO,
               'UPSTREAM_BRANCH': UPSTREAM_BRANCH,
               'UPGRADE_PACKAGES': UPGRADE_PACKAGES,
               'USER_SESSION_STRING': USER_SESSION_STRING}

if ospath.exists('buttons.txt'):
    with open('buttons.txt', 'r+') as f:
        lines = f.readlines()
        for line in lines:
            temp = line.strip().rsplit(maxsplit=1)
            if len(extra_buttons.keys()) >= 20:
                break
            elif len(temp) == 2 and temp[1].startswith('http'):
                extra_buttons[temp[0]] = temp[1]

# Tiny health-check web server: Heroku / Render / Railway all need something listening on $PORT.
PORT = environ.get('PORT') or '8080'
Popen(f"gunicorn web.wserver:app --bind 0.0.0.0:{PORT} --worker-class gevent", shell=True)
alive = Popen(["python3", "alive.py"])
sleep(0.5)

log_info("Creating client from BOT_TOKEN")
# update workers are cheap asyncio tasks (old fast repo: 1000). 50 made busy bots queue commands.
def _new_bot():
    return wztgClient('bot', TELEGRAM_API, TELEGRAM_HASH, bot_token=BOT_TOKEN, workers=int(environ.get('TG_WORKERS', '1000') or 1000),
                      parse_mode=enums.ParseMode.HTML)


def _start_bot_floodsafe():
    from pyrogram.errors import FloodWait as _FW
    while True:
        try:
            return tg_start(_new_bot())
        except _FW as _f:
            log_warning(f"Telegram FloodWait on login: sleeping {_f.value}s")
            bot_loop.run_until_complete(__import__('asyncio').sleep(_f.value + 1))


try:
    bot = _start_bot_floodsafe()
except Exception as _e:
    # A restart can leave a half-written bot.session (sqlite: "no such table: version").
    # The session of a bot token is disposable: delete it and log in again.
    if 'sqlite' in repr(_e).lower() or 'no such table' in str(_e).lower() or 'database' in str(_e).lower():
        log_error(f"Broken bot session file ({_e}); deleting it and logging in again")
        from glob import glob as _glob
        from os import remove as _remove
        for _f in _glob('bot.session*'):
            try:
                _remove(_f)
            except Exception:
                pass
        bot = _start_bot_floodsafe()
    else:
        raise


# Every command/callback handler runs as its own task. Without this a slow handler
# (FloodWait sleep, long await, ...) keeps a dispatcher worker busy and new commands
# are answered only 1-2 minutes later while the running tasks keep working fine.
# Works the same on pyrofork and wzgram.
def _spawn_handler(callback):
    if getattr(callback, '_spawned', False):
        return callback

    async def _run(client, args, kwargs):
        try:
            # how old is the update when its handler finally starts? (loop lag / queue / network)
            _d = getattr(args[0], 'date', None) if args else None
            if _d is not None:
                _age = time() - _d.timestamp()
                if _age > 4:
                    LOGGER.warning(f"Slow response: {getattr(callback, '__name__', 'handler')} started {_age:.1f}s after the message was sent")
        except Exception:
            pass
        try:
            res = callback(client, *args, **kwargs)
            if iscoroutine(res):
                await res
        except Exception as e:
            LOGGER.error(f"Handler {getattr(callback, '__name__', callback)} failed: {e}", exc_info=True)

    @wraps(callback)
    async def wrapper(client, *args, **kwargs):
        bot_loop.create_task(_run(client, args, kwargs))

    wrapper._spawned = True
    return wrapper


_orig_add_handler = bot.add_handler


def _add_handler(handler, group=0):
    try:
        cb = handler.callback
        if cb is not None and (iscoroutinefunction(cb) or getattr(cb, '_is_new_task', False)):
            handler.callback = _spawn_handler(cb)
    except Exception as e:
        LOGGER.error(f"add_handler wrap skipped: {e}")
    return _orig_add_handler(handler, group)


bot.add_handler = _add_handler

def _global_asyncio_error_handler(loop, context):
    """
    Safety-net for exceptions raised in fire-and-forget background tasks
    (e.g. anything scheduled with bot_loop.create_task / the @new_task
    decorator) that nobody ever awaits/checks the result of. Without this,
    such errors are only visible as a generic, hard-to-trace
    "Task exception was never retrieved" line. This logs them properly
    instead, and never lets a single bad task crash the whole event loop.
    """
    exc = context.get('exception')
    msg = context.get('message', 'Unhandled exception in background task')
    if exc:
        LOGGER.error(f"{msg}: {exc}", exc_info=exc)
    else:
        LOGGER.error(msg)

bot_loop.set_exception_handler(_global_asyncio_error_handler)

def _patch_pyrogram_listener_future_bug():
    """
    Works around a pyrofork bug (confirmed upstream, not something in this
    bot's own code) where CallbackQueryHandler/MessageHandler's internal
    resolve_future_or_callback() sometimes ends up doing
    `await self.original_callback(...)` while self.original_callback is
    actually an asyncio.Future (used by pyrofork's own listen()/ask()
    machinery), not our registered callback function. That raises
    "TypeError: object Future can't be used in 'await' expression".

    This just logs and drops the update instead of crashing. An earlier
    version of this patch tried to be "helpful" by calling our real handler
    directly when this happened - but there's no way to know from here
    whether pyrofork's own internal resolve logic already ran (part of) our
    handler before hitting this error, so that risked *double-invoking*
    state-changing handlers (toggle buttons flipping on then straight back
    off, settings getting reset right after being set, etc.) - a correctness
    bug that's worse than the button occasionally needing a retry. Dropping
    the update safely (as before) is the right tradeoff here.

    This must run before any of our modules register their handlers
    (bot/modules/*.py), since it patches the class - handlers created after
    this point pick up the safe version automatically.
    """
    try:
        from pyrogram.handlers.callback_query_handler import CallbackQueryHandler
        from pyrogram.handlers.message_handler import MessageHandler
    except Exception as e:
        log_error(f"Could not patch pyrogram Future/callback dispatch bug (import failed): {e}")
        return

    from asyncio import Future

    patched_any = False
    for handler_cls in (CallbackQueryHandler, MessageHandler):
        original_resolve = getattr(handler_cls, 'resolve_future_or_callback', None)
        if original_resolve is None:
            continue

        async def patched_resolve(self, client, update, *args, _orig=original_resolve):
            cb = getattr(self, 'original_callback', None)
            # If this handler's callback is actually a pending Future
            # (pyrofork's own listen()/ask() usage), resolve it directly
            # instead of trying to await it.
            if isinstance(cb, Future):
                if not cb.done():
                    cb.set_result(update)
                return
            try:
                await _orig(self, client, update, *args)
            except TypeError as e:
                if "Future" in str(e):
                    LOGGER.warning(f"Swallowed pyrofork Future/callback dispatch bug (dropped this update - please retry): {e}")
                else:
                    raise

        handler_cls.resolve_future_or_callback = patched_resolve
        patched_any = True

    if patched_any:
        log_info("Patched pyrogram/pyrofork Future-vs-callback dispatch bug.")

_patch_pyrogram_listener_future_bug()

bot_name = bot.me.username
scheduler = AsyncIOScheduler(timezone=str(get_localzone()), event_loop=bot_loop)
