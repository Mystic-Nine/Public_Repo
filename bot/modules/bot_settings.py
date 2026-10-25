#!/usr/bin/env python3
from random import choice
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex, create
from pyrogram.enums import ChatType
from functools import partial
from collections import OrderedDict
from asyncio import create_subprocess_exec, create_subprocess_shell, sleep, gather
from aiofiles.os import remove, rename, path as aiopath
from aiofiles import open as aiopen
from os import environ, getcwd
from dotenv import load_dotenv
from time import time
from io import BytesIO
from aioshutil import rmtree as aiormtree

from bot import config_dict, user_data, DATABASE_URL, MAX_SPLIT_SIZE, GLOBAL_EXTENSION_FILTER, status_reply_dict_lock, Interval, IS_PREMIUM_USER, download_dict, LOGGER, bot, extra_buttons
from bot.helper.telegram_helper.message_utils import sendMessage, sendFile, editMessage, deleteMessage, update_all_messages
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import setInterval, sync_to_async, new_thread
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.task_manager import start_from_queued
from bot.helper.ext_utils.help_messages import default_desp
from bot.helper.themes import AVL_THEMES

START = 0
STATE = 'view'
handler_dict = {}
default_values = {'AUTO_DELETE_MESSAGE_DURATION': 30,
                  'DOWNLOAD_DIR': '/usr/src/app/downloads/',
                  'LEECH_SPLIT_SIZE': MAX_SPLIT_SIZE,
                  'STATUS_UPDATE_INTERVAL': 5,
                  'UPSTREAM_BRANCH': 'update',
                  'BOT_THEME': 'minimal',
                  'BOT_LANG': 'en',
                  'IMG_PAGE': 1,
                  'AUTHOR_NAME': 'ʀᴀʀᴇ ʙᴏᴛꜱ ʜᴜʙ',
                  'AUTHOR_URL': 'https://t.me/Rare_Bots_Hub',
                  'TITLE_NAME': 'ʀᴀʀᴇ ʙᴏᴛꜱ ʜᴜʙ',
                  }
bool_vars = ['AS_DOCUMENT', 'BOT_PM', 'SET_COMMANDS', 'SAVE_MSG', 'SHOW_MEDIAINFO', 'SOURCE_LINK', 'SAFE_MODE', 'SHOW_EXTRA_CMDS',
             'EQUAL_SPLITS', 'DELETE_LINKS', 'CLEAN_LOG_MSG', 'MEDIA_GROUP',
             'INCOMPLETE_TASK_NOTIFIER', 'UPGRADE_PACKAGES', 'SCREENSHOTS_MODE']


async def load_config():

    BOT_TOKEN = environ.get('BOT_TOKEN', '')
    if len(BOT_TOKEN) == 0:
        BOT_TOKEN = config_dict['BOT_TOKEN']

    TELEGRAM_API = environ.get('TELEGRAM_API', '')
    if len(TELEGRAM_API) == 0:
        TELEGRAM_API = config_dict['TELEGRAM_API']
    else:
        TELEGRAM_API = int(TELEGRAM_API)

    TELEGRAM_HASH = environ.get('TELEGRAM_HASH', '')
    if len(TELEGRAM_HASH) == 0:
        TELEGRAM_HASH = config_dict['TELEGRAM_HASH']

    BOT_MAX_TASKS = environ.get('BOT_MAX_TASKS', '')
    BOT_MAX_TASKS = int(BOT_MAX_TASKS) if BOT_MAX_TASKS.isdigit() else ''
    
    OWNER_ID = environ.get('OWNER_ID', '')
    OWNER_ID = config_dict['OWNER_ID'] if len(OWNER_ID) == 0 else int(OWNER_ID)

    DATABASE_URL = environ.get('DATABASE_URL', '')
    if len(DATABASE_URL) == 0:
        DATABASE_URL = ''

    DOWNLOAD_DIR = environ.get('DOWNLOAD_DIR', '')
    if len(DOWNLOAD_DIR) == 0:
        DOWNLOAD_DIR = '/usr/src/app/downloads/'
    elif not DOWNLOAD_DIR.endswith("/"):
        DOWNLOAD_DIR = f'{DOWNLOAD_DIR}/'

    AUTHORIZED_CHATS = environ.get('AUTHORIZED_CHATS', '')
    if len(AUTHORIZED_CHATS) != 0:
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
        aid = BLACKLIST_USERS.split()
        for id_ in aid:
            user_data[int(id_.strip())] = {'is_blacklist': True}

    EXTENSION_FILTER = environ.get('EXTENSION_FILTER', '')
    if len(EXTENSION_FILTER) > 0:
        fx = EXTENSION_FILTER.split()
        GLOBAL_EXTENSION_FILTER.clear()
        for x in fx:
            x = x.lstrip('.')
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())

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
    if len(LEECH_SPLIT_SIZE) == 0 or int(LEECH_SPLIT_SIZE) > MAX_SPLIT_SIZE:
        LEECH_SPLIT_SIZE = MAX_SPLIT_SIZE
    else:
        LEECH_SPLIT_SIZE = int(LEECH_SPLIT_SIZE)

    STATUS_UPDATE_INTERVAL = environ.get('STATUS_UPDATE_INTERVAL', '')
    if len(STATUS_UPDATE_INTERVAL) == 0:
        STATUS_UPDATE_INTERVAL = 5
    else:
        STATUS_UPDATE_INTERVAL = int(STATUS_UPDATE_INTERVAL)
    if len(download_dict) != 0:
        async with status_reply_dict_lock:
            if Interval:
                Interval[0].cancel()
                Interval.clear()
                Interval.append(setInterval(STATUS_UPDATE_INTERVAL, update_all_messages))

    AUTO_DELETE_MESSAGE_DURATION = environ.get(
        'AUTO_DELETE_MESSAGE_DURATION', '')
    if len(AUTO_DELETE_MESSAGE_DURATION) == 0:
        AUTO_DELETE_MESSAGE_DURATION = 30
    else:
        AUTO_DELETE_MESSAGE_DURATION = int(AUTO_DELETE_MESSAGE_DURATION)

    STATUS_LIMIT = environ.get('STATUS_LIMIT', '')
    STATUS_LIMIT = 10 if len(STATUS_LIMIT) == 0 else int(STATUS_LIMIT)

    CMD_SUFFIX = environ.get('CMD_SUFFIX', '')

    USER_SESSION_STRING = environ.get('USER_SESSION_STRING', '')

    QUEUE_ALL = environ.get('QUEUE_ALL', '')
    QUEUE_ALL = '' if len(QUEUE_ALL) == 0 else int(QUEUE_ALL)

    QUEUE_DOWNLOAD = environ.get('QUEUE_DOWNLOAD', '')
    QUEUE_DOWNLOAD = '' if len(QUEUE_DOWNLOAD) == 0 else int(QUEUE_DOWNLOAD)

    QUEUE_UPLOAD = environ.get('QUEUE_UPLOAD', '')
    QUEUE_UPLOAD = '' if len(QUEUE_UPLOAD) == 0 else int(QUEUE_UPLOAD)

    INCOMPLETE_TASK_NOTIFIER = environ.get('INCOMPLETE_TASK_NOTIFIER', '')
    INCOMPLETE_TASK_NOTIFIER = INCOMPLETE_TASK_NOTIFIER.lower() == 'true'
    if not INCOMPLETE_TASK_NOTIFIER and DATABASE_URL:
        await DbManger().trunc_table('tasks')

    AS_DOCUMENT = environ.get('AS_DOCUMENT', 'true')
    AS_DOCUMENT = AS_DOCUMENT.lower() == 'true'
    
    SHOW_MEDIAINFO = environ.get('SHOW_MEDIAINFO', '')
    SHOW_MEDIAINFO = SHOW_MEDIAINFO.lower() == 'true'
    
    SHOW_MEDIAINFO = environ.get('SHOW_MEDIAINFO', '')
    SHOW_MEDIAINFO = SHOW_MEDIAINFO.lower() == 'true'
    
    SOURCE_LINK = environ.get('SOURCE_LINK', '')
    SOURCE_LINK = SOURCE_LINK.lower() == 'true'

    DELETE_LINKS = environ.get('DELETE_LINKS', '')
    DELETE_LINKS = DELETE_LINKS.lower() == 'true'

    EQUAL_SPLITS = environ.get('EQUAL_SPLITS', '')
    EQUAL_SPLITS = EQUAL_SPLITS.lower() == 'true'

    MEDIA_GROUP = environ.get('MEDIA_GROUP', '')
    MEDIA_GROUP = MEDIA_GROUP.lower() == 'true'

    BASE_URL = environ.get('BASE_URL', '').rstrip("/")

    UPSTREAM_REPO = environ.get('UPSTREAM_REPO', '')
    if len(UPSTREAM_REPO) == 0:
        UPSTREAM_REPO = ''

    UPSTREAM_BRANCH = environ.get('UPSTREAM_BRANCH', '')
    if len(UPSTREAM_BRANCH) == 0:
        UPSTREAM_BRANCH = 'kpsmlx'

    UPGRADE_PACKAGES = environ.get('UPGRADE_PACKAGES', '')
    UPGRADE_PACKAGES = UPGRADE_PACKAGES.lower() == 'true'

    STORAGE_THRESHOLD = environ.get('STORAGE_THRESHOLD', '')
    STORAGE_THRESHOLD = '' if len(
        STORAGE_THRESHOLD) == 0 else float(STORAGE_THRESHOLD)

    LEECH_LIMIT = environ.get('LEECH_LIMIT', '')
    LEECH_LIMIT = '' if len(LEECH_LIMIT) == 0 else float(LEECH_LIMIT)

    FSUB_IDS = environ.get('FSUB_IDS', '')
    if len(FSUB_IDS) == 0:
        FSUB_IDS = ''
    
    LINKS_LOG_ID = environ.get('LINKS_LOG_ID', '')
    LINKS_LOG_ID = '' if len(LINKS_LOG_ID) == 0 else int(LINKS_LOG_ID)

    LEECH_LOG_ID = environ.get('LEECH_LOG_ID', '')
    if len(LEECH_LOG_ID) == 0:
        LEECH_LOG_ID = ''
        
    EXCEP_CHATS = environ.get('EXCEP_CHATS', '')
    if len(EXCEP_CHATS) == 0:
        EXCEP_CHATS = ''

    USER_MAX_TASKS = environ.get('USER_MAX_TASKS', '')
    USER_MAX_TASKS = int(USER_MAX_TASKS) if USER_MAX_TASKS.isdigit() else ''

    USER_TIME_INTERVAL = environ.get('USER_TIME_INTERVAL', '')
    USER_TIME_INTERVAL = int(USER_TIME_INTERVAL) if USER_TIME_INTERVAL.isdigit() else 0

    BOT_PM = environ.get('BOT_PM', 'true')
    BOT_PM = BOT_PM.lower() == 'true'

    DAILY_TASK_LIMIT = environ.get('DAILY_TASK_LIMIT', '')
    DAILY_TASK_LIMIT = '' if len(DAILY_TASK_LIMIT) == 0 else int(DAILY_TASK_LIMIT)

    DAILY_LEECH_LIMIT = environ.get('DAILY_LEECH_LIMIT', '')
    DAILY_LEECH_LIMIT = '' if len(DAILY_LEECH_LIMIT) == 0 else float(DAILY_LEECH_LIMIT)

    BOT_THEME = environ.get('BOT_THEME', '')
    if len(BOT_THEME) == 0:
        BOT_THEME = 'minimal'

    IMG_SEARCH = environ.get('IMG_SEARCH', '')
    IMG_SEARCH = (IMG_SEARCH.replace("'", '').replace('"', '').replace('[', '').replace(']', '').replace(",", "")).split()
    
    IMG_PAGE = environ.get('IMG_PAGE', '')
    IMG_PAGE = int(IMG_PAGE) if IMG_PAGE.isdigit() else ''

    IMAGES = environ.get('IMAGES', '')
    IMAGES = (IMAGES.replace("'", '').replace('"', '').replace('[', '').replace(']', '').replace(",", "")).split()

    AUTHOR_NAME = environ.get('AUTHOR_NAME', '')
    if len(AUTHOR_NAME) == 0:
        AUTHOR_NAME = 'Rare Bots Hub'

    AUTHOR_URL = environ.get('AUTHOR_URL', '')
    if len(AUTHOR_URL) == 0:
        AUTHOR_URL = 'https://telegram.me/Rare_Bots_Hub'

    TITLE_NAME = environ.get('TITLE_NAME', '')
    if len(TITLE_NAME) == 0:
        TITLE_NAME = 'KPSML-X Leech Bot'
        
    COVER_IMAGE = environ.get('COVER_IMAGE', '')
    if len(COVER_IMAGE) == 0:
        COVER_IMAGE = 'https://graph.org/file/0ff9d5e94a070fe4154c0.jpg'

    SAVE_MSG = environ.get('SAVE_MSG', '')
    SAVE_MSG = SAVE_MSG.lower() == 'true'

    SET_COMMANDS = environ.get('SET_COMMANDS', '')
    SET_COMMANDS = SET_COMMANDS.lower() == 'true'
    
    SAFE_MODE = environ.get('SAFE_MODE', '')
    SAFE_MODE = SAFE_MODE.lower() == 'true'
    
    SCREENSHOTS_MODE = environ.get('SCREENSHOTS_MODE', '')
    SCREENSHOTS_MODE = SCREENSHOTS_MODE.lower() == 'true'

    CLEAN_LOG_MSG = environ.get('CLEAN_LOG_MSG', '')
    CLEAN_LOG_MSG = CLEAN_LOG_MSG.lower() == 'true'
    
    SHOW_EXTRA_CMDS = environ.get('SHOW_EXTRA_CMDS', '')
    SHOW_EXTRA_CMDS = SHOW_EXTRA_CMDS.lower() == 'true'
    
    TOKEN_TIMEOUT = environ.get('TOKEN_TIMEOUT', '')
    TOKEN_TIMEOUT = int(TOKEN_TIMEOUT) if TOKEN_TIMEOUT.isdigit() else ''

    LOGIN_PASS = environ.get('LOGIN_PASS', '')
    if len(LOGIN_PASS) == 0:
        LOGIN_PASS = None

    TMDB_API_KEY = environ.get('TMDB_API_KEY', '')
    if len(TMDB_API_KEY) == 0:
        TMDB_API_KEY = ''

    DEF_IMDB_TEMP  = environ.get('IMDB_TEMPLATE', '')
    if len(DEF_IMDB_TEMP) == 0:
        DEF_IMDB_TEMP = '''<b>Title: </b> {title} [{year}]
<b>Also Known As:</b> {aka}
<b>Rating ⭐️:</b> <i>{rating}</i>
<b>Release Info: </b> <a href="{url_releaseinfo}">{release_date}</a>
<b>Genre: </b>{genres}
<b>IMDb URL:</b> {url}
<b>Language: </b>{languages}
<b>Country of Origin : </b> {countries}

<b>Story Line: </b><code>{plot}</code>

<a href="{url_cast}">Read More ...</a>'''

    DEF_ANI_TEMP  = environ.get('ANIME_TEMPLATE', '')
    if len(DEF_ANI_TEMP) == 0:
        DEF_ANI_TEMP = '''<b>{ro_title}</b>({na_title})
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
    
    TIMEZONE = environ.get('TIMEZONE', '')
    if len(TIMEZONE) == 0:
        TIMEZONE = 'Asia/Kolkata'
        
    extra_buttons.clear()
    if await aiopath.exists('buttons.txt'):
        async with aiopen('buttons.txt', 'r+') as f:
            lines = await f.readlines()
            for line in lines:
                temp = line.strip().split()
                if len(extra_buttons.keys()) == 4:
                    break
                if len(temp) == 2:
                    extra_buttons[temp[0].replace("_", " ")] = temp[1]

    config_dict.update({'ANIME_TEMPLATE': DEF_ANI_TEMP,
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
                        'TMDB_API_KEY': TMDB_API_KEY,
                        'DELETE_LINKS': DELETE_LINKS,
                        'DOWNLOAD_DIR': DOWNLOAD_DIR,
                        'EXCEP_CHATS': EXCEP_CHATS,
                        'STORAGE_THRESHOLD': STORAGE_THRESHOLD,
                        'LEECH_LIMIT': LEECH_LIMIT,
                        'FSUB_IDS': FSUB_IDS,
                        'USER_MAX_TASKS': USER_MAX_TASKS,
                        'USER_TIME_INTERVAL': USER_TIME_INTERVAL,
                        'DAILY_TASK_LIMIT': DAILY_TASK_LIMIT,
                        'DAILY_LEECH_LIMIT': DAILY_LEECH_LIMIT,
                        'LEECH_LOG_ID': LEECH_LOG_ID,
                        'LINKS_LOG_ID': LINKS_LOG_ID,
                        'BOT_PM': BOT_PM,
                        'BOT_THEME': BOT_THEME,
                        'IMAGES': IMAGES,
                        'IMG_SEARCH': IMG_SEARCH,
                        'IMG_PAGE': IMG_PAGE,
                        'IMDB_TEMPLATE': DEF_IMDB_TEMP,
                        'AUTHOR_NAME': AUTHOR_NAME,
                        'AUTHOR_URL': AUTHOR_URL,
                        'COVER_IMAGE': COVER_IMAGE,
                        'TITLE_NAME': TITLE_NAME,
                        'EQUAL_SPLITS': EQUAL_SPLITS,
                        'EXTENSION_FILTER': EXTENSION_FILTER,
                        'INCOMPLETE_TASK_NOTIFIER': INCOMPLETE_TASK_NOTIFIER,
                        'METADATA': METADATA,
                        'ATTACHMENT': ATTACHMENT,
                        'LEECH_FILENAME_PREFIX': LEECH_FILENAME_PREFIX,
                        'LEECH_FILENAME_SUFFIX': LEECH_FILENAME_SUFFIX,
                        'LEECH_FILENAME_CAPTION': LEECH_FILENAME_CAPTION,
                        'LEECH_FILENAME_REMNAME': LEECH_FILENAME_REMNAME,
                        'LEECH_SPLIT_SIZE': LEECH_SPLIT_SIZE,
                        'LOGIN_PASS': LOGIN_PASS,
                        'TOKEN_TIMEOUT': TOKEN_TIMEOUT,
                        'MEDIA_GROUP': MEDIA_GROUP,
                        'MDL_TEMPLATE': MDL_TEMPLATE,
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
                        'TIMEZONE': TIMEZONE,
                        'UPSTREAM_REPO': UPSTREAM_REPO,
                        'UPSTREAM_BRANCH': UPSTREAM_BRANCH,
                        'UPGRADE_PACKAGES': UPGRADE_PACKAGES,
                        'USER_SESSION_STRING': USER_SESSION_STRING})

    if DATABASE_URL:
        await DbManger().update_config(config_dict)
    await start_from_queued()


async def get_buttons(key=None, edit_type=None, edit_mode=None, mess=None):
    buttons = ButtonMaker()
    if key is None:
        buttons.ibutton('Config Variables', "botset var")
        buttons.ibutton('Private Files', "botset private")
        buttons.ibutton('Close', "botset close")
        msg = '<b><i>Bot Settings:</i></b>'
    elif key == 'var':
        for k in list(OrderedDict(sorted(config_dict.items())).keys())[START:10+START]:
            buttons.ibutton(k, f"botset editvar {k}")
        buttons.ibutton('Back', "botset back")
        buttons.ibutton('Close', "botset close")
        for x in range(0, len(config_dict)-1, 10):
            buttons.ibutton(f'{int(x/10)+1}', f"botset start var {x}", position='footer')
        msg = f'<b>Config Variables</b> | <b>Page: {int(START/10)+1}</b>'
    elif key == 'private':
        buttons.ibutton('Back', "botset back")
        buttons.ibutton('Close', "botset close")
        msg = '''<u>Send any of these private files:</u>
        
<code>config.env, buttons.txt, kpsml_*.py theme files or any other file!</code>

<i>To delete private file send only the file name as text message with or without extension.</i>

<b>Timeout:</b> 60 sec'''
    elif edit_type == 'editvar':
        msg = f'<b>Variable:</b> <code>{key}</code>\n\n'
        msg += f'<b>Description:</b> {default_desp.get(key, "No Description Provided")}\n\n'
        if mess.chat.type == ChatType.PRIVATE:
            msg += f'<b>Value:</b> <spoiler> {config_dict.get(key, "None")} </spoiler>\n\n'
        else:
            buttons.ibutton('View Var Value',
                            f"botset showvar {key}", position="header")
        buttons.ibutton('Back', "botset back var", position="footer")
        if key not in bool_vars:
            if not edit_mode:
                buttons.ibutton('Edit Value', f"botset editvar {key} edit")
            else:
                buttons.ibutton('Stop Edit', f"botset editvar {key}")
        if key not in ['TELEGRAM_HASH', 'TELEGRAM_API', 'OWNER_ID', 'BOT_TOKEN'] and key not in bool_vars:
            buttons.ibutton('Reset', f"botset resetvar {key}")
        buttons.ibutton('Close', "botset close", position="footer")
        if edit_mode and key in ['SUDO_USERS', 'CMD_SUFFIX', 'OWNER_ID', 'USER_SESSION_STRING', 'TELEGRAM_HASH',
                                 'TELEGRAM_API', 'AUTHORIZED_CHATS', 'DATABASE_URL', 'BOT_TOKEN', 'DOWNLOAD_DIR']:
            msg += '<b>Note:</b> Restart required for this edit to take effect!\n\n'
        if edit_mode and key not in bool_vars:
            msg += '<i>Send a valid value for the above Var.</i> <b>Timeout:</b> 60 sec'
        if key in bool_vars:
            msg += '<i>Choose a valid value for the above Var</i>'
            buttons.ibutton('True', f"botset boolvar {key} on")
            buttons.ibutton('False', f"botset boolvar {key} off")
    button = buttons.build_menu(1) if key is None else buttons.build_menu(2)
    return msg, button


async def update_buttons(message, key=None, edit_type=None, edit_mode=None):
    msg, button = await get_buttons(key, edit_type, edit_mode, message)
    await editMessage(message, msg, button)


async def edit_variable(_, message, pre_message, key):
    handler_dict[message.chat.id] = False
    value = message.text
    if key == 'DOWNLOAD_DIR':
        if not value.endswith('/'):
            value += '/'
    elif key in ['LINKS_LOG_ID']:
        value = int(value)
    elif key == 'STATUS_UPDATE_INTERVAL':
        value = int(value)
        if len(download_dict) != 0:
            async with status_reply_dict_lock:
                if Interval:
                    Interval[0].cancel()
                    Interval.clear()
                    Interval.append(setInterval(value, update_all_messages))
    elif key == 'LEECH_SPLIT_SIZE':
        value = min(int(value), MAX_SPLIT_SIZE)
    elif key == 'BOT_THEME':
        if not value.strip() in AVL_THEMES.keys():
            value = 'minimal'
    elif key == 'CAP_FONT':
        value = value.strip().lower()
        if value not in ['b', 'i', 'u', 's', 'spoiler', 'code']:
            value = 'code'
    elif key == 'EXTENSION_FILTER':
        fx = value.split()
        GLOBAL_EXTENSION_FILTER.clear()
        for x in fx:
            if x.strip().startswith('.'):
                x = x.lstrip('.')
            GLOBAL_EXTENSION_FILTER.append(x.strip().lower())
    elif key == 'IMAGES':
        # Must end up as a list of URLs, same parsing as the startup value in
        # bot/__init__.py - the generic fallback below just stores the raw
        # text as one string, and random.choice() on a plain string picks a
        # random *character* (sometimes a newline between URLs), which then
        # fails to send as a photo on essentially every other status/start
        # message. Splitting on whitespace also drops blank lines for free.
        value = (value.replace("'", '').replace('"', '').replace(
            '[', '').replace(']', '').replace(",", "")).split()
    elif value.isdigit():
        value = int(value)
    config_dict[key] = value
    await update_buttons(pre_message, key, 'editvar', False)
    await deleteMessage(message)
    if DATABASE_URL:
        await DbManger().update_config({key: value})
    if key in ['QUEUE_ALL', 'QUEUE_DOWNLOAD', 'QUEUE_UPLOAD']:
        await start_from_queued()


async def update_private_file(_, message, pre_message):
    handler_dict[message.chat.id] = False
    if not message.media and (file_name := message.text):
        path = file_name
        fn = file_name.rsplit('.zip', 1)[0]
        if await aiopath.isfile(fn) and file_name != 'config.env':
            await remove(fn)
        if file_name.startswith('kpsml_'):
            path = f"bot/helper/themes/{file_name.rsplit('.py', 1)[0]}.py"
            if await aiopath.isfile(path):
                await remove(path)
        elif file_name in ['buttons.txt', 'buttons']:
            extra_buttons.clear()
        await deleteMessage(message)
    elif doc := message.document:
        file_name = doc.file_name
        path = file_name
        if file_name.startswith('kpsml_') and file_name.endswith('.py'):
            path = f'bot/helper/themes/{file_name}'
        await message.download(file_name=f'{getcwd()}/{path}')
        if file_name == 'buttons.txt':
            extra_buttons.clear()
            async with aiopen('buttons.txt', 'r+') as f:
                lines = await f.readlines()
                for line in lines:
                    temp = line.strip().rsplit(maxsplit=1)
                    if len(extra_buttons.keys()) >= 20:
                        break
                    elif temp[1].startswith('http'):
                        extra_buttons[temp[0]] = temp[1]
        elif file_name == 'config.env':
            load_dotenv('config.env', override=True)
            await load_config()
        if '@github.com' in config_dict['UPSTREAM_REPO']:
            buttons = ButtonMaker()
            msg = '<i>Do you want to Upload (Git Push) your file to <b>UPSTREAM_REPO</b> ?</i>'
            buttons.ibutton('Yes!', f"botset push {file_name}")
            buttons.ibutton('No!', "botset close")
            await sendMessage(message, msg, buttons.build_menu(2))
        else:
            await deleteMessage(message)
    await update_buttons(pre_message)
    if DATABASE_URL:
        await DbManger().update_private_file(path)


async def event_handler(client, query, pfunc, rfunc, document=False):
    chat_id = query.message.chat.id
    handler_dict[chat_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        user = event.from_user or event.sender_chat
        return bool(user.id == query.from_user.id and event.chat.id == chat_id and (event.text or event.document and document))
    handler = client.add_handler(MessageHandler(
        pfunc, filters=create(event_filter)), group=-1)
    while handler_dict[chat_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[chat_id] = False
            await rfunc()
    client.remove_handler(*handler)


@new_thread
async def edit_bot_settings(client, query):
    data = query.data.split()
    message = query.message
    if data[1] == 'close':
        handler_dict[message.chat.id] = False
        await query.answer()
        await deleteMessage(message)
        await deleteMessage(message.reply_to_message)
    elif data[1] == 'back':
        handler_dict[message.chat.id] = False
        await query.answer()
        key = data[2] if len(data) == 3 else None
        if key is None:
            globals()['START'] = 0
        await update_buttons(message, key)
    elif data[1] == 'var':
        await query.answer()
        await update_buttons(message, data[1])
    elif data[1] == 'resetvar':
        handler_dict[message.chat.id] = False
        await query.answer('Reset Done!', show_alert=True)
        value = ''
        if data[2] in default_values:
            value = default_values[data[2]]
            if data[2] == "STATUS_UPDATE_INTERVAL" and len(download_dict) != 0:
                async with status_reply_dict_lock:
                    if Interval:
                        Interval[0].cancel()
                        Interval.clear()
                        Interval.append(setInterval(
                            value, update_all_messages))
        elif data[2] == 'EXTENSION_FILTER':
            GLOBAL_EXTENSION_FILTER.clear()
        elif data[2] == 'INCOMPLETE_TASK_NOTIFIER' and DATABASE_URL:
            await DbManger().trunc_table('tasks')
        config_dict[data[2]] = value
        await update_buttons(message, data[2], 'editvar', False)
        if DATABASE_URL:
            await DbManger().update_config({data[2]: value})
        if data[2] in ['QUEUE_ALL', 'QUEUE_DOWNLOAD', 'QUEUE_UPLOAD']:
            await start_from_queued()
    elif data[1] == 'private':
        handler_dict[message.chat.id] = False
        await query.answer()
        await update_buttons(message, data[1])
        pfunc = partial(update_private_file, pre_message=message)
        rfunc = partial(update_buttons, message)
        await event_handler(client, query, pfunc, rfunc, True)
    elif data[1] == 'boolvar':
        handler_dict[message.chat.id] = False
        value = data[3] == "on"
        await query.answer(f'Successfully Var changed to {value}!', show_alert=True)
        config_dict[data[2]] = value
        if not value and data[2] == 'INCOMPLETE_TASK_NOTIFIER' and DATABASE_URL:
            await DbManger().trunc_table('tasks')
        await update_buttons(message, data[2], 'editvar', False)
        if DATABASE_URL:
            await DbManger().update_config({data[2]: value})
    elif data[1] == 'editvar':
        handler_dict[message.chat.id] = False
        await query.answer()
        edit_mode = len(data) == 4
        await update_buttons(message, data[2], data[1], edit_mode)
        if data[2] in bool_vars or not edit_mode:
            return
        pfunc = partial(edit_variable, pre_message=message, key=data[2])
        rfunc = partial(update_buttons, message, data[2], data[1], edit_mode)
        await event_handler(client, query, pfunc, rfunc)
    elif data[1] == 'showvar':
        value = config_dict[data[2]]
        if len(str(value)) > 200:
            await query.answer()
            with BytesIO(str.encode(value)) as out_file:
                out_file.name = f"{data[2]}.txt"
                await sendFile(message, out_file)
            return
        elif value == '':
            value = None
        await query.answer(f'{value}', show_alert=True)
    elif data[1] == 'edit':
        await query.answer()
        globals()['STATE'] = 'edit'
        await update_buttons(message, data[2])
    elif data[1] == 'view':
        await query.answer()
        globals()['STATE'] = 'view'
        await update_buttons(message, data[2])
    elif data[1] == 'start':
        await query.answer()
        if START != int(data[3]):
            globals()['START'] = int(data[3])
            await update_buttons(message, data[2])
    elif data[1] == 'push':
        await query.answer()
        filename = data[2].rsplit('.zip', 1)[0]
        if await aiopath.exists(filename):
            await (await create_subprocess_shell(f"git add -f {filename} \
                                                   && git commit -sm botsettings -q \
                                                   && git push origin {config_dict['UPSTREAM_BRANCH']} -qf")).wait()
        else:
            await (await create_subprocess_shell(f"git rm -r --cached {filename} \
                                                   && git commit -sm botsettings -q \
                                                   && git push origin {config_dict['UPSTREAM_BRANCH']} -qf")).wait()
        await deleteMessage(message)
        await deleteMessage(message.reply_to_message)


async def bot_settings(_, message):
    msg, button = await get_buttons()
    globals()['START'] = 0
    await sendMessage(message, msg, button, 'IMAGES')


bot.add_handler(MessageHandler(bot_settings, filters=command(
    BotCommands.BotSetCommand) & CustomFilters.sudo))
bot.add_handler(CallbackQueryHandler(edit_bot_settings,
                filters=regex("^botset") & CustomFilters.sudo))
