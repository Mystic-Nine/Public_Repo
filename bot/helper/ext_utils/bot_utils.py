#!/usr/bin/env python3
import platform
from base64 import b64encode
from datetime import datetime
from os import path as ospath
from importlib.metadata import version as _pkg_version, PackageNotFoundError
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove, path as aiopath, mkdir
from re import match as re_match
from time import time
from html import escape
from uuid import uuid4
from subprocess import run as srun
from psutil import disk_usage, disk_io_counters, Process, cpu_percent, swap_memory, cpu_count, cpu_freq, getloadavg, virtual_memory, net_io_counters, boot_time
from asyncio import create_subprocess_exec, create_subprocess_shell, run_coroutine_threadsafe, sleep
from asyncio.subprocess import PIPE
from functools import partial, wraps
from concurrent.futures import ThreadPoolExecutor

from aiohttp import ClientSession as aioClientSession
from psutil import virtual_memory, cpu_percent, disk_usage
from requests import get as rget
from pyrogram.enums import ChatType
from pyrogram.types import BotCommand
from pyrogram.errors import PeerIdInvalid

from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.themes import BotTheme
from bot.version import get_version
from bot import OWNER_ID, bot_name, bot_cache, DATABASE_URL, LOGGER, download_dict, download_dict_lock, botStartTime, user_data, config_dict, bot_loop, extra_buttons, user
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.telegraph_helper import telegraph

THREADPOOL   = ThreadPoolExecutor(max_workers=int(__import__('os').environ.get('THREADPOOL_SIZE', '32') or 32))
UI_POOL      = ThreadPoolExecutor(max_workers=4)   # status text only, never starved by heavy tasks
URL_REGEX    = r'^(?!\/)(rtmps?:\/\/|mms:\/\/|rtsp:\/\/|https?:\/\/|ftp:\/\/)?([^\/:]+:[^\/@]+@)?(www\.)?(?=[^\/:\s]+\.[^\/:\s]+)([^\/:\s]+\.[^\/:\s]+)(:\d+)?(\/[^#\s]*[\s\S]*)?(\?[^#\s]*)?(#.*)?$'
SIZE_UNITS   = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']
STATUS_START = 0
PAGES        = 1
PAGE_NO      = 1


class TaskStatus:
    STATUS_UPLOADING   = "Upload"
    STATUS_DOWNLOADING = "Download"
    STATUS_QUEUEDL     = "QueueDL"
    STATUS_QUEUEUP     = "QueueUp"
    STATUS_PAUSED      = "Pause"
    STATUS_ARCHIVING   = "Archive"
    STATUS_EXTRACTING  = "Extract"
    STATUS_SPLITTING   = "Split"
    STATUS_CHECKING    = "CheckUp"
    STATUS_METADATA    = "Metadata"
    STATUS_ATTACHMENT  = "Attachment"


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.task = bot_loop.create_task(self.__set_interval())

    async def __set_interval(self):
        while True:
            await sleep(self.interval)
            await self.action()

    def cancel(self):
        self.task.cancel()


def get_readable_file_size(size_in_bytes):
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1
    return f'{size_in_bytes:.2f}{SIZE_UNITS[index]}' if index > 0 else f'{size_in_bytes}B'


async def getDownloadByGid(gid):
    async with download_dict_lock:
        return next((dl for dl in download_dict.values() if dl.gid() == gid), None)


async def getAllDownload(req_status, user_id=None):
    dls = []
    async with download_dict_lock:
        for dl in list(download_dict.values()):
            if user_id and user_id != dl.message.from_user.id:
                continue
            status = dl.status()
            if req_status in ['all', status]:
                dls.append(dl)
    return dls


async def get_user_tasks(user_id, maxtask):
    if tasks := await getAllDownload('all', user_id):
        return len(tasks) >= maxtask


def handleIndex(index, dic):
    while True:
        if abs(index) >= len(dic):
            if index < 0: index = len(dic) - abs(index)
            elif index > 0: index = index - len(dic)
        else: break
    return index

def get_progress_bar_string(pct):
    pct = float(str(pct).strip('%'))
    p = min(max(pct, 0), 100)
    cFull = int(p // 8)
    cPart = int(p % 8 - 1)
    p_str = '■' * cFull
    if cPart >= 0:
        p_str += ['▤', '▥', '▦', '▧', '▨', '▩', '■'][cPart]
    p_str += '□' * (12 - cFull)
    return f"[{p_str}]"


def get_all_versions():
    try:
        result = srun(['7z', '-version'], capture_output=True, text=True)
        vp = result.stdout.split('\n')[2].split(' ')[2]
    except Exception:
        vp = ''
    try:
        result = srun(['ffmpeg', '-version'], capture_output=True, text=True)
        vf = result.stdout.split('\n')[0].split(' ')[2].split('ubuntu')[0]
    except Exception:
        vf = ''
    vpy = "2.xx.xx"
    for dist in ('wzgram', 'pyrofork', 'pyrogram'):
        try:
            vpy = _pkg_version(dist)
            break
        except PackageNotFoundError:
            continue
    try:
        vaio = _pkg_version('aiohttp')
    except PackageNotFoundError:
        vaio = ''
    bot_cache['eng_versions'] = {'p7zip': vp, 'ffmpeg': vf, 'aiohttp': vaio, 'pyro': vpy}


class EngineStatus:
    def __init__(self):
        if not (version_cache := bot_cache.get('eng_versions')):
            get_all_versions()
            version_cache = bot_cache.get('eng_versions')
        self.STATUS_AIOHTTP = f"AioHttp {version_cache['aiohttp']}"
        self.STATUS_TG = f"PyroMulti v{version_cache['pyro']}"
        self.STATUS_EXT = "pExtract v2"
        self.STATUS_SPLIT_MERGE = f"ffmpeg v{version_cache['ffmpeg']}"
        self.STATUS_ZIP = f"p7zip v{version_cache['p7zip']}"
        self.STATUS_QUEUE = "Sleep v0"


def get_readable_message():
    msg = ""
    button = None
    STATUS_LIMIT = config_dict['STATUS_LIMIT']
    tasks = len(download_dict)
    globals()['PAGES'] = (tasks + STATUS_LIMIT - 1) // STATUS_LIMIT
    if PAGE_NO > PAGES and PAGES != 0:
        globals()['STATUS_START'] = STATUS_LIMIT * (PAGES - 1)
        globals()['PAGE_NO'] = PAGES
    _all = list(download_dict.values())
    _st = {}  # call status() once per task
    for download in _all[STATUS_START:STATUS_LIMIT+STATUS_START]:
        _st[id(download)] = dstatus = download.status()
        msg_link = download.message.link if download.message.chat.type in [
            ChatType.SUPERGROUP, ChatType.CHANNEL] and not config_dict['DELETE_LINKS'] else ''
        elapsed = time() - download.message.date.timestamp()
        msg += BotTheme('STATUS_NAME', Name="Task is being Processed!" if config_dict['SAFE_MODE'] and elapsed >= config_dict['STATUS_UPDATE_INTERVAL'] else escape(f'{download.name()}'))
        if dstatus != TaskStatus.STATUS_SPLITTING:
            msg += BotTheme('BAR', Bar=f"{get_progress_bar_string(download.progress())} {download.progress()}")
            msg += BotTheme('PROCESSED', Processed=f"{download.processed_bytes()} of {download.size()}")
            msg += BotTheme('STATUS', Status=dstatus, Url=msg_link)
            msg += BotTheme('ETA', Eta=download.eta())
            msg += BotTheme('SPEED', Speed=download.speed())
            msg += BotTheme('ELAPSED', Elapsed=get_readable_time(elapsed))
            msg += BotTheme('ENGINE', Engine=download.eng())
            msg += BotTheme('STA_MODE', Mode=download.upload_details['mode'])
        else:
            msg += BotTheme('STATUS', Status=dstatus, Url=msg_link)
            msg += BotTheme('STATUS_SIZE', Size=download.size())
            msg += BotTheme('NON_ENGINE', Engine=download.eng())

        msg += BotTheme('USER',
                        User=download.message.from_user.mention(style="html"))
        msg += BotTheme('ID', Id=download.message.from_user.id)
        msg += BotTheme('CANCEL', Cancel=f"/{BotCommands.CancelTask}_{download.gid()}")

    if len(msg) == 0:
        return None, None

    dl_speed = 0

    def convert_speed_to_bytes_per_second(spd):
        if 'K' in spd:
            return float(spd.split('K')[0]) * 1024
        elif 'M' in spd:
            return float(spd.split('M')[0]) * 1048576
        elif 'G' in spd:
            return float(spd.split('G')[0]) * 1073741824
        elif 'T' in spd:
            return float(spd.split('T')[0]) * 1099511627776
        else:
            return 0

    dl_speed = 0
    up_speed = 0
    for download in _all:
        tstatus = _st[id(download)] if id(download) in _st else download.status()
        spd = download.speed()
        speed_in_bytes_per_second = convert_speed_to_bytes_per_second(spd)
        ud = getattr(download, 'upload_details', None)
        if tstatus == TaskStatus.STATUS_DOWNLOADING:
            dl_speed += speed_in_bytes_per_second
            if isinstance(ud, dict) and speed_in_bytes_per_second > (ud.get('max_dl') or 0):
                ud['max_dl'] = speed_in_bytes_per_second
        elif tstatus == TaskStatus.STATUS_UPLOADING:
            if isinstance(ud, dict) and speed_in_bytes_per_second > (ud.get('max_ul') or 0):
                ud['max_ul'] = speed_in_bytes_per_second
            up_speed += speed_in_bytes_per_second

    msg += BotTheme('FOOTER')
    buttons = ButtonMaker()
    buttons.ibutton(BotTheme('REFRESH', Page=f"{PAGE_NO}/{PAGES}"), "status ref")
    if tasks > STATUS_LIMIT:
        if config_dict['BOT_MAX_TASKS']:
            msg += BotTheme('BOT_TASKS', Tasks=tasks, Ttask=config_dict['BOT_MAX_TASKS'], Free=config_dict['BOT_MAX_TASKS']-tasks)
        else:
            msg += BotTheme('TASKS', Tasks=tasks)
        buttons = ButtonMaker()
        buttons.ibutton(BotTheme('PREVIOUS'), "status pre")
        buttons.ibutton(BotTheme('REFRESH', Page=f"{PAGE_NO}/{PAGES}"), "status ref")
        buttons.ibutton(BotTheme('NEXT'), "status nex")
    button = buttons.build_menu(3)
    msg += BotTheme('Cpu', cpu=cpu_percent())
    msg += BotTheme('FREE', free=get_readable_file_size(disk_usage(config_dict['DOWNLOAD_DIR']).free), free_p=round(100-disk_usage(config_dict['DOWNLOAD_DIR']).percent, 1))
    msg += BotTheme('Ram', ram=virtual_memory().percent)
    msg += BotTheme('uptime', uptime=get_readable_time(time() - botStartTime))
    msg += BotTheme('DL', DL=get_readable_file_size(dl_speed))
    msg += BotTheme('UL', UL=get_readable_file_size(up_speed))
    return msg, button


async def turn_page(data):
    STATUS_LIMIT = config_dict['STATUS_LIMIT']
    global STATUS_START, PAGE_NO
    async with download_dict_lock:
        if data[1] == "nex":
            if PAGE_NO == PAGES:
                STATUS_START = 0
                PAGE_NO = 1
            else:
                STATUS_START += STATUS_LIMIT
                PAGE_NO += 1
        elif data[1] == "pre":
            if PAGE_NO == 1:
                STATUS_START = STATUS_LIMIT * (PAGES - 1)
                PAGE_NO = PAGES
            else:
                STATUS_START -= STATUS_LIMIT
                PAGE_NO -= 1


def get_readable_time(seconds):
    periods = [('d', 86400), ('h', 3600), ('m', 60), ('s', 1)]
    result = ''
    for period_name, period_seconds in periods:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            result += f'{int(period_value)}{period_name}'
    return result


def is_url(url):
    return bool(re_match(URL_REGEX, url))


def is_telegram_link(url):
    return url.startswith(('https://t.me/', 'https://telegram.me/', 'https://telegram.dog/', 'https://telegram.space/', 'tg://openmessage?user_id='))


def arg_parser(items, arg_base):
    if not items:
        return arg_base
    bool_arg_set = {'-b', '-e', '-z', '-s', '-j', '-d'}
    t = len(items)
    i = 0
    arg_start = -1

    while i + 1 <= t:
        part = items[i].strip()
        if part in arg_base:
            if arg_start == -1:
                arg_start = i
            if i + 1 == t and part in bool_arg_set or part in ['-s', '-j']:
                arg_base[part] = True
            else:
                sub_list = []
                for j in range(i + 1, t):
                    item = items[j].strip()
                    if item in arg_base:
                        if part in bool_arg_set and not sub_list:
                            arg_base[part] = True
                        break
                    sub_list.append(item.strip())
                    i += 1
                if sub_list:
                    arg_base[part] = " ".join(sub_list)
        i += 1

    link = []
    if items[0].strip() not in arg_base:
        if arg_start == -1:
            link.extend(item.strip() for item in items)
        else:
            link.extend(items[r].strip() for r in range(arg_start))
        if link:
            arg_base['link'] = " ".join(link)
    return arg_base


def update_user_ldata(id_, key=None, value=None):
    exception_keys = ['is_sudo', 'is_auth', 'dly_tasks', 'is_blacklist', 'token', 'time']
    if key is None and value is None:
        if id_ in user_data:
            updated_data = {}
            for k, v in user_data[id_].items():
                if k in exception_keys:
                    updated_data[k] = v
            user_data[id_] = updated_data
        return
    user_data.setdefault(id_, {})
    user_data[id_][key] = value


async def download_image_url(url):
    path = "Images/"
    if not await aiopath.isdir(path):
        await mkdir(path)
    image_name = url.split('/')[-1]
    des_dir = ospath.join(path, image_name)
    async with aioClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                async with aiopen(des_dir, 'wb') as file:
                    async for chunk in response.content.iter_chunked(1024):
                        await file.write(chunk)
                LOGGER.info(f"Image Downloaded Successfully as {image_name}")
            else:
                LOGGER.error(f"Failed to Download Image from {url}")
    return des_dir


async def cmd_exec(cmd, shell=False):
    if shell:
        proc = await create_subprocess_shell(cmd, stdout=PIPE, stderr=PIPE)
    else:
        proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await proc.communicate()
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()
    return stdout, stderr, proc.returncode


def new_task(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return bot_loop.create_task(func(*args, **kwargs))
    wrapper._is_new_task = True
    return wrapper


async def sync_to_async(func, *args, wait=True, **kwargs):
    pfunc = partial(func, *args, **kwargs)
    future = bot_loop.run_in_executor(THREADPOOL, pfunc)
    return await future if wait else future


def async_to_sync(func, *args, wait=True, **kwargs):
    future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
    return future.result() if wait else future


def new_thread(func):
    @wraps(func)
    def wrapper(*args, wait=False, **kwargs):
        future = run_coroutine_threadsafe(func(*args, **kwargs), bot_loop)
        return future.result() if wait else future
    return wrapper


async def compare_versions(v1, v2):
    try:
        v1_parts = [int(x) for x in __import__('re').findall(r'\d+', str(v1).split('-')[0])][:3]
        v2_parts = [int(x) for x in __import__('re').findall(r'\d+', str(v2).split('-')[0])][:3]
        if len(v1_parts) < 3 or len(v2_parts) < 3:
            return "Version check unavailable right now"
    except Exception:
        return "Version check unavailable right now"
    for i in range(3):
        v1_part, v2_part = v1_parts[i], v2_parts[i]
        if v1_part < v2_part:
            return "New Version Update is Available! Check Now!"
        elif v1_part > v2_part:
            return "More Updated! Kindly Contribute in Official"
    return "Already up to date with latest version"


async def get_stats(event, key="home"):
    user_id = event.from_user.id
    btns = ButtonMaker()
    btns.ibutton('Back', f'kpsmlx {user_id} stats home')
    if key == "home":
        btns = ButtonMaker()
        btns.ibutton('Bot Stats', f'kpsmlx {user_id} stats stbot')
        btns.ibutton('OS Stats', f'kpsmlx {user_id} stats stsys')
        btns.ibutton('Repo Stats', f'kpsmlx {user_id} stats strepo')
        btns.ibutton('Bot Limits', f'kpsmlx {user_id} stats botlimits')
        msg = "⌬ <b><i>Bot & OS Statistics!</i></b>"
    elif key == "stbot":
        total, used, free, disk = disk_usage('/')
        swap = swap_memory()
        memory = virtual_memory()
        disk_io = disk_io_counters()
        msg = BotTheme(
            'BOT_STATS',
            bot_uptime=get_readable_time(time() - botStartTime),
            ram_bar=get_progress_bar_string(memory.percent),
            ram=memory.percent,
            ram_u=get_readable_file_size(memory.used),
            ram_f=get_readable_file_size(memory.available),
            ram_t=get_readable_file_size(memory.total),
            swap_bar=get_progress_bar_string(swap.percent),
            swap=swap.percent,
            swap_u=get_readable_file_size(swap.used),
            swap_f=get_readable_file_size(swap.free),
            swap_t=get_readable_file_size(swap.total),
            disk=disk,
            disk_bar=get_progress_bar_string(disk),
            disk_read=f"{get_readable_file_size(disk_io.read_bytes)} ({get_readable_time(disk_io.read_time / 1000)})"
            if disk_io
            else "Access Denied",
            disk_write=f"{get_readable_file_size(disk_io.write_bytes)} ({get_readable_time(disk_io.write_time / 1000)})"
            if disk_io
            else "Access Denied",
            disk_t=get_readable_file_size(total),
            disk_u=get_readable_file_size(used),
            disk_f=get_readable_file_size(free),
        )
    elif key == "stsys":
        cpuUsage = cpu_percent(interval=0.5)
        msg = BotTheme('SYS_STATS',
            os_uptime=get_readable_time(time() - boot_time()),
            os_version=platform.version(),
            os_arch=platform.platform(),
            up_data=get_readable_file_size(net_io_counters().bytes_sent),
            dl_data=get_readable_file_size(net_io_counters().bytes_recv),
            pkt_sent=str(net_io_counters().packets_sent)[:-3],
            pkt_recv=str(net_io_counters().packets_recv)[:-3],
            tl_data=get_readable_file_size(net_io_counters().bytes_recv + net_io_counters().bytes_sent),
            cpu=cpuUsage,
            cpu_bar=get_progress_bar_string(cpuUsage),
            cpu_freq=f"{cpu_freq(percpu=False).current / 1000:.2f} GHz" if cpu_freq() else "Access Denied",
            sys_load="%, ".join(str(round((x / cpu_count() * 100), 2)) for x in getloadavg()) + "%, (1m, 5m, 15m)",
            p_core=cpu_count(logical=False),
            v_core=cpu_count(logical=True) - cpu_count(logical=False),
            total_core=cpu_count(logical=True),
            cpu_use=len(Process().cpu_affinity()),
        )
    elif key == "strepo":
        last_commit, changelog = 'No Data', 'N/A'
        if await aiopath.exists('.git'):
            last_commit = (await cmd_exec("git log -1 --pretty='%cd ( %cr )' --date=format-local:'%d/%m/%Y'", True))[0]
            changelog = (await cmd_exec("git log -1 --pretty=format:'<code>%s</code> <b>By</b> %an'", True))[0]
        official_v = (await cmd_exec("curl -o latestversion.py https://github.com/Tamilupdates/KPSML-X/raw/refs/heads/kpsmlx/bot/version.py -s && python3 latestversion.py && rm latestversion.py", True))[0]
        msg = BotTheme('REPO_STATS',
            last_commit=last_commit,
            bot_version=get_version(),
            lat_version=official_v,
            commit_details=changelog,
            remarks=await compare_versions(get_version(), official_v),
        )
    elif key == "botlimits":
        msg = BotTheme('BOT_LIMITS',
                LL = ('∞' if (val := config_dict['LEECH_LIMIT']) == '' else val),
                TV  = ('Disabled' if (val := config_dict['TOKEN_TIMEOUT']) == '' else get_readable_time(val)),
                UTI = ('Disabled' if (val := config_dict['USER_TIME_INTERVAL']) == 0 else get_readable_time(val)),
                UT = ('∞' if (val := config_dict['USER_MAX_TASKS']) == '' else val),
                BT = ('∞' if (val := config_dict['BOT_MAX_TASKS']) == '' else val),
        )
    btns.ibutton('Close', f'kpsmlx {user_id} close')
    return msg, btns.build_menu(2)


async def getdailytasks(user_id, increase_task=False, upleech=0, upmirror=0, check_mirror=False, check_leech=False):
    task, lsize, msize = 0, 0, 0
    if user_id in user_data and user_data[user_id].get('dly_tasks'):
        userdate, task, lsize, msize = user_data[user_id]['dly_tasks']
        nowdate = datetime.now()
        if userdate.year <= nowdate.year and userdate.month <= nowdate.month and userdate.day < nowdate.day:
            task, lsize, msize = 0, 0, 0
            if increase_task:
                task = 1
            elif upleech != 0:
                lsize += upleech
            elif upmirror != 0:
                msize += upmirror
        elif increase_task:
            task += 1
        elif upleech != 0:
            lsize += upleech
        elif upmirror != 0:
            msize += upmirror
    elif increase_task:
        task += 1
    elif upleech != 0:
        lsize += upleech
    elif upmirror != 0:
        msize += upmirror
    update_user_ldata(user_id, 'dly_tasks', [datetime.now(), task, lsize, msize])
    if DATABASE_URL:
        await DbManger().update_user_data(user_id)
    if check_leech:
        return lsize
    elif check_mirror:
        return msize
    return task


async def fetch_user_dumps(user_id):
    user_dict = user_data.get(user_id, {})
    if (dumps := user_dict.get('ldump', False)):
        if not isinstance(dumps, dict):
            update_user_ldata(user_id, 'ldump', {})
            return {}
        return dumps
    return {}


async def checking_access(user_id, button=None):
    if not config_dict['TOKEN_TIMEOUT'] or bool(user_id == OWNER_ID or user_id in user_data and user_data[user_id].get('is_sudo')):
        return None, button
    user_data.setdefault(user_id, {})
    data = user_data[user_id]
    expire = data.get('time')
    if config_dict['LOGIN_PASS'] is not None and data.get('token', '') == config_dict['LOGIN_PASS']:
        return None, button
    isExpired = (expire is None or expire is not None and (time() - expire) > config_dict['TOKEN_TIMEOUT'])
    if isExpired:
        token = data['token'] if expire is None and 'token' in data else str(uuid4())
        if expire is not None:
            del data['time']
        data['token'] = token
        user_data[user_id].update(data)
        if button is None:
            button = ButtonMaker()
        encrypt_url = b64encode(f"{token}&&{user_id}".encode()).decode()
        button.ubutton('Generate New Token', f'https://t.me/{bot_name}?start={encrypt_url}')
        return f'<i>Temporary Token has been expired,</i> Kindly generate a New Temp Token to start using bot Again.\n<b>Validity :</b> <code>{get_readable_time(config_dict["TOKEN_TIMEOUT"])}</code>', button
    return None, button


def extra_btns(buttons, already=False):
    if extra_buttons and not already:
        for btn_name, btn_url in extra_buttons.items():
            buttons.ubutton(btn_name, btn_url, 'l_body')
    return buttons, True



async def set_commands(client):
    if not config_dict['SET_COMMANDS']:
        return
    try:
        bot_cmds = [
            BotCommand(BotCommands.LeechCommand[0], f'or /{BotCommands.LeechCommand[1]} Leech a replied Telegram file/link'),
            BotCommand(BotCommands.StatusCommand[0], f'or /{BotCommands.StatusCommand[1]} Get Bot All Status Stats Message'),
            BotCommand(BotCommands.StatsCommand[0], f'or /{BotCommands.StatsCommand[1]} Check Bot & System stats'),
            BotCommand(BotCommands.CancelTask, 'Cancel a Task of yours!'),
            BotCommand(BotCommands.CancelAllCommand[0], 'Cancel all Tasks in whole Bots.'),
            BotCommand(BotCommands.HelpCommand, 'Get detailed help about the Bot'),
            BotCommand(BotCommands.UserSetCommand[0], f"or /{BotCommands.UserSetCommand[1]} User's Personal Settings (Open in PM)"),
            BotCommand(BotCommands.IMDBCommand, 'Search Movies/Series on IMDB.com and fetch details'),
            BotCommand(BotCommands.AniListCommand, 'Search Animes on AniList.com and fetch details'),
            BotCommand(BotCommands.MyDramaListCommand, 'Search Dramas on MyDramaList.com and fetch details'),
            BotCommand(BotCommands.PosterCommand, 'Search Movie/TV Show Poster via TMDB'),
            BotCommand(BotCommands.SpeedCommand[0], f'or /{BotCommands.SpeedCommand[1]} Check Server Up & Down Speed & Details'),
            BotCommand(BotCommands.MediaInfoCommand[0], f'or /{BotCommands.MediaInfoCommand[1]} Generate Mediainfo for Replied Media'),
            BotCommand(BotCommands.BotSetCommand[0], f"or /{BotCommands.BotSetCommand[1]} Bot's Personal Settings (Owner or Sudo Only)"),
            BotCommand(BotCommands.RestartCommand[0], f'or /{BotCommands.RestartCommand[1]} Restart the Bot (Owner or Sudo Only)'),
        ]
        if config_dict['SHOW_EXTRA_CMDS']:
            bot_cmds.insert(1, BotCommand(BotCommands.LeechCommand[2], f'or /{BotCommands.LeechCommand[3]} Leech and UnZip'))
            bot_cmds.insert(1, BotCommand(BotCommands.LeechCommand[4], f'or /{BotCommands.LeechCommand[5]} Leech and Zip'))
        await client.set_bot_commands(bot_cmds)
        LOGGER.info('Bot Commands have been Set & Updated')
    except Exception as err:
        LOGGER.error(err)


_LINK_RE = __import__('re').compile(r'(https?://[^\s<>"]+)', __import__('re').IGNORECASE)


def find_link_in_message(msg):
    """First link/magnet anywhere in a (text) message: plain text, then hidden text_link entities.
    Falls back to the old behaviour (first line). Never raises."""
    try:
        text = (msg.text or '').strip()
        found = [m.group(1).strip() for m in _LINK_RE.finditer(text)]
        if found:
            # a bare https://t.me/Channel (footer/credit link) is not something to download: prefer another link
            real = [u for u in found if not __import__('re').match(r'^https?://(t|telegram)\.(me|dog)/[A-Za-z0-9_]+/?$', u, __import__('re').I)]
            return (real or found)[0]
        for e in (msg.entities or []):
            if getattr(getattr(e, 'type', None), 'name', '') == 'TEXT_LINK' and getattr(e, 'url', None):
                return e.url
        return text.split('\n', 1)[0].strip()
    except Exception:
        return ''


async def contribute_link(name, link, size_text):
    """WZML-X 'contribute' feature: POSTs every shared Drive link (+ name, size) to a third-party
    site. It used to run on the event loop for every such task. Now OFF unless CONTRIBUTE_LINKS=true."""
    if __import__('os').environ.get('CONTRIBUTE_LINKS', 'false').lower() != 'true':
        return
    def _post():
        from cloudscraper import create_scraper
        from json import dumps
        create_scraper().request('POST', "https://wzmlcontribute.vercel.app/contribute", timeout=15,
                                 headers={"Content-Type": "application/json"},
                                 data=dumps({"name": name, "link": link, "size": size_text}))
    try:
        await sync_to_async(_post)
    except Exception:
        pass


def save_jpeg(src, dst):
    """Open + convert + save an image (runs in a worker thread: Pillow work used to run on the event loop)."""
    from PIL import Image
    with Image.open(src) as im:
        im.convert("RGB").save(dst, "JPEG")


