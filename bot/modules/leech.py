from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from html import escape
from traceback import format_exc
from asyncio import sleep, wrap_future
from aiofiles import open as aiopen
from cloudscraper import create_scraper

from bot import bot, DOWNLOAD_DIR, LOGGER, bot_name
from bot.helper.ext_utils.bot_utils import find_link_in_message, new_task, is_telegram_link, arg_parser, fetch_user_dumps, get_stats
from bot.helper.ext_utils.task_manager import task_utils
from bot.helper.tg_utils.download_utils.telegram_download import TelegramDownloadHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, editReplyMarkup, deleteMessage, get_tg_link_content, delete_links, open_dump_btns
from bot.helper.listeners.tasks_listener import LeechListener
from bot.helper.ext_utils.help_messages import LEECH_HELP_MESSAGE, help_string
from bot.helper.ext_utils.bulk_links import extract_bulk_links
from bot.modules.gen_pyro_sess import get_decrypt_key


@new_task
async def _leech(client, message, sameDir=None, bulk=[]):
    text = message.text.split('\n')
    input_list = text[0].split(' ')

    arg_base = {'link': '',
                '-i': '0',
                '-m': '', '-sd': '', '-samedir': '',
                '-b': False, '-bulk': False,
                '-n': '', '-name': '', '|': '',
                '-e': False, '-extract': False,
                '-uz': False, '-unzip': False,
                '-z': False, '-zip': False,
                '-up': '', '-upload': '',
                '-ud': '', '-dump': '',
                '-ss': '0', '-screenshots': '',
                '-t': '', '-thumb': '',
    }

    args = arg_parser(input_list[1:], arg_base)
    cmd = input_list[0].split('@')[0]

    multi = int(args['-i']) if args['-i'].isdigit() else 0

    link          = args['link']
    folder_name   = args['-m'] or args['-sd'] or args['-samedir']
    isBulk        = args['-b'] or args['-bulk']
    name          = args['-n'] or args['-name'] or args['|']
    extract       = args['-e'] or args['-extract'] or args['-uz'] or args['-unzip'] or 'uz' in cmd or 'unzip' in cmd
    compress      = args['-z'] or args['-zip'] or (not extract and ('z' in cmd or 'zip' in cmd))
    up            = args['-up'] or args['-upload']
    user_dump     = args['-ud'] or args['-dump']
    thumb         = args['-t'] or args['-thumb']
    sshots        = int(ss) if (ss := (args['-ss'] or args['-screenshots'])).isdigit() else 0
    bulk_start    = 0
    bulk_end      = 0
    reply_to      = None
    file_         = None
    session       = ''

    if not isinstance(isBulk, bool):
        dargs = isBulk.split(':')
        bulk_start = dargs[0] or None
        if len(dargs) == 2:
            bulk_end = dargs[1] or None
        isBulk = True

    if folder_name and not isBulk:
        folder_name = f'/{folder_name}'
        if sameDir is None:
            sameDir = {'total': multi, 'tasks': set(), 'name': folder_name}
        sameDir['tasks'].add(message.id)

    if isBulk:
        try:
            bulk = await extract_bulk_links(message, bulk_start, bulk_end)
            if len(bulk) == 0:
                raise ValueError('Bulk Empty!')
        except:
            await sendMessage(message, 'Reply to text file or tg message that have Telegram links seperated by new line!')
            return
        b_msg = input_list[:1]
        b_msg.append(f'{bulk[0]} -i {len(bulk)}')
        nextmsg = await sendMessage(message, " ".join(b_msg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        nextmsg.from_user = message.from_user
        _leech(client, nextmsg, sameDir, bulk)
        return

    if len(bulk) != 0:
        del bulk[0]

    @new_task
    async def __run_multi():
        if multi <= 1:
            return
        await sleep(5)
        if len(bulk) != 0:
            msg = input_list[:1]
            msg.append(f'{bulk[0]} -i {multi - 1}')
            nextmsg = await sendMessage(message, " ".join(msg))
        else:
            msg = [s.strip() for s in input_list]
            index = msg.index('-i')
            msg[index+1] = f"{multi - 1}"
            nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id + 1)
            nextmsg = await sendMessage(nextmsg, " ".join(msg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        if folder_name:
            sameDir['tasks'].add(nextmsg.id)
        nextmsg.from_user = message.from_user
        await sleep(5)
        _leech(client, nextmsg, sameDir, bulk)

    __run_multi()

    path = f'{DOWNLOAD_DIR}{message.id}{folder_name}'

    if len(text) > 1 and text[1].startswith('Tag: '):
        tag, id_ = text[1].split('Tag: ')[1].split()
        message.from_user = await client.get_users(id_)
        try:
            await message.unpin()
        except:
            pass
    elif sender_chat := message.sender_chat:
        tag = sender_chat.title
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    decrypter = None
    if not link and (reply_to := message.reply_to_message):
        if reply_to.text:
            link = find_link_in_message(reply_to)
    if link and is_telegram_link(link):
        try:
            reply_to, session = await get_tg_link_content(link, message.from_user.id)
            if reply_to is None and session == "":
                decrypter, is_cancelled = await wrap_future(get_decrypt_key(client, message))
                if is_cancelled:
                    return
                reply_to, session = await get_tg_link_content(link, message.from_user.id, decrypter)
        except Exception as e:
            LOGGER.info(format_exc())
            await sendMessage(message, f'<b>ERROR:</b> <i>{e}</i>')
            await delete_links(message)
            return

    if reply_to:
        # a text message with a link has media=WEB_PAGE (link preview): that is not a file
        has_media = reply_to.media and reply_to.media.value != 'web_page'
        file_ = getattr(reply_to, reply_to.media.value) if has_media else None

    if file_ is None:
        btn = ButtonMaker()
        btn.ibutton('Cʟɪᴄᴋ Hᴇʀᴇ Tᴏ Rᴇᴀᴅ Mᴏʀᴇ ...', f'kpsmlx {message.from_user.id} help LEECH')
        await sendMessage(message, LEECH_HELP_MESSAGE[0], btn.build_menu(1))
        await delete_links(message)
        return

    error_msg = []
    error_button = None
    task_utilis_msg, error_button = await task_utils(message)
    if task_utilis_msg:
        error_msg.extend(task_utilis_msg)

    if error_msg:
        final_msg = f'<b><i>User:</i> {tag}</b>,\n'
        for __i, __msg in enumerate(error_msg, 1):
            final_msg += f'\n<b>{__i}</b>: {__msg}\n'
        if error_button is not None:
            error_button = error_button.build_menu(2)
        await sendMessage(message, final_msg, error_button)
        await delete_links(message)
        return

    if user_dump and (user_dump.isdigit() or user_dump.startswith('-')):
        up = int(user_dump)
    elif user_dump and user_dump.startswith('@'):
        up = user_dump
    elif (ldumps := await fetch_user_dumps(message.from_user.id)):
        if user_dump and user_dump.casefold() == "all":
            up = [dump_id for dump_id in ldumps.values()]
        elif user_dump:
            up = next((dump_id for name_, dump_id in ldumps.items() if user_dump.casefold() == name_.casefold()), '')
        if not up and len(ldumps) == 1:
            up = next(iter(ldumps.values()))
        elif not up:
            up, is_cancelled = await open_dump_btns(message)
            if is_cancelled:
                await delete_links(message)
                return

    listener = LeechListener(message, compress, extract, tag, sameDir, up, source_url=link or None,
                             leech_utils={'screenshots': sshots, 'thumb': thumb}, newname=name)
    listener.orig_caption = reply_to.caption or ""
    await delete_links(message)
    await TelegramDownloadHelper(listener).add_download(reply_to, f'{path}/', name, session, decrypter)


@new_task
async def kpsmlxcb(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != int(data[1]):
        return await query.answer(text="Not Yours!", show_alert=True)
    elif data[2] == "logdisplay":
        await query.answer()
        async with aiopen('log.txt', 'r') as f:
            logFileLines = (await f.read()).splitlines()
        def parseline(line):
            try:
                return "[" + line.split('] [', 1)[1]
            except IndexError:
                return line
        ind, Loglines = 1, ''
        try:
            while len(Loglines) <= 3500:
                Loglines = parseline(logFileLines[-ind]) + '\n' + Loglines
                if ind == len(logFileLines): 
                    break
                ind += 1
            startLine = f"<b>Showing Last {ind} Lines from log.txt:</b> \n\n----------<b>START LOG</b>----------\n\n"
            endLine = "\n----------<b>END LOG</b>----------"
            btn = ButtonMaker()
            btn.ibutton('Cʟᴏsᴇ', f'kpsmlx {user_id} close')
            await sendMessage(message, startLine + escape(Loglines) + endLine, btn.build_menu(1))
            await editReplyMarkup(message, None)
        except Exception as err:
            LOGGER.error(f"TG Log Display : {str(err)}")
    elif data[2] == "webpaste":
        await query.answer()
        try:
            async with aiopen('log.txt', 'r') as f:
                logFile = await f.read()
            cget = create_scraper().request
            resp = cget('POST', 'https://spaceb.in/api/v1/documents', data={'content': logFile, 'extension': 'None'}).json()
            if resp['status'] == 201:
                btn = ButtonMaker()
                btn.ubutton('📨 Web Paste (SB)', f"https://spaceb.in/{resp['payload']['id']}")
                await editReplyMarkup(message, btn.build_menu(1))
            else:
                LOGGER.error(f"Web Paste Failed : {resp}")
        except Exception as err:
            LOGGER.error(f"Web Paste Failed : {str(err)}")
    elif data[2] == "botpm":
        await query.answer(url=f"https://t.me/{bot_name}?start=kpsmlx")
    elif data[2] == "help":
        await query.answer()
        btn = ButtonMaker()
        btn.ibutton('Cʟᴏsᴇ', f'kpsmlx {user_id} close')
        if data[3] == "LEECH":
            if len(data) == 4:
                msg = LEECH_HELP_MESSAGE[1][:4000]
                if len(LEECH_HELP_MESSAGE[1]) > 4000:
                    btn.ibutton('Nᴇxᴛ Pᴀɢᴇ', f'kpsmlx {user_id} help LEECH readmore')
            else:
                msg = LEECH_HELP_MESSAGE[1][4000:]
                btn.ibutton('Pʀᴇ Pᴀɢᴇ', f'kpsmlx {user_id} help LEECH')
            await editMessage(message, msg, btn.build_menu(2))
    elif data[2] == "guide":
        btn = ButtonMaker()
        btn.ibutton('Bᴀᴄᴋ', f'kpsmlx {user_id} guide home')
        btn.ibutton('Cʟᴏsᴇ', f'kpsmlx {user_id} close')
        if data[3] == "basic":
            await editMessage(message, help_string[0], btn.build_menu(2))
        elif data[3] == "users":
            await editMessage(message, help_string[1], btn.build_menu(2))
        elif data[3] == "miscs":
            await editMessage(message, help_string[3], btn.build_menu(2))
        elif data[3] == "admin":
            if not await CustomFilters.sudo('', query):
                return await query.answer('Not Sudo or Owner!', show_alert=True)
            await editMessage(message, help_string[2], btn.build_menu(2))
        else:
            buttons = ButtonMaker()
            buttons.ibutton('Basic', f'kpsmlx {user_id} guide basic')
            buttons.ibutton('Users', f'kpsmlx {user_id} guide users')
            buttons.ibutton('Mics', f'kpsmlx {user_id} guide miscs')
            buttons.ibutton('Owner & Sudos', f'kpsmlx {user_id} guide admin')
            buttons.ibutton('Close', f'kpsmlx {user_id} close')
            await editMessage(message, "㊂ <b><i>Help Guide Menu!</i></b>\n\n<b>NOTE: <i>Click on any CMD to see more minor detalis.</i></b>", buttons.build_menu(2))
        await query.answer()
    elif data[2] == "stats":
        msg, btn = await get_stats(query, data[3])
        await editMessage(message, msg, btn, 'IMAGES')
    else:
        await query.answer()
        await deleteMessage(message)
        if message.reply_to_message:
            await deleteMessage(message.reply_to_message)
            if message.reply_to_message.reply_to_message:
                await deleteMessage(message.reply_to_message.reply_to_message)


async def leech(client, message):
    _leech(client, message)


bot.add_handler(MessageHandler(leech, filters=command(
    BotCommands.LeechCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))
bot.add_handler(CallbackQueryHandler(kpsmlxcb, filters=regex(r'^kpsmlx')))
