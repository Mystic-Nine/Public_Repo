#!/usr/bin/env python3
from pyrogram.filters import regex
from pyrogram.handlers import CallbackQueryHandler
from time import time

from bot import bot, bot_cache
from bot.helper.ext_utils.bot_utils import fetch_user_dumps, new_task, get_readable_time
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import editMessage


@new_task
async def confirm_dump(client, query):
    user_id = query.from_user.id
    data = query.data.split(maxsplit=3)
    msg_id = int(data[2])
    if msg_id not in bot_cache:
        return await editMessage(query.message, '<b>Old Task</b>')
    elif user_id != int(data[1]) and not await CustomFilters.sudo(client, query):
        return await query.answer(text="This task is not for you!", show_alert=True)
    elif data[3] == "ddone":
        bot_cache[msg_id][1] = True
        return
    elif data[3] == "dcancel":
        bot_cache[msg_id][2] = True
        return
    await query.answer()
    user_dumps = await fetch_user_dumps(user_id)
    cat_name = data[3].replace('_', ' ')
    upall = cat_name == "All"
    bot_cache[msg_id][0] = list(user_dumps.values()) if upall else user_dumps[cat_name]
    buttons = ButtonMaker()
    if user_dumps:
        for _name in user_dumps.keys():
            buttons.ibutton(f'{"✅️" if upall or cat_name == _name else ""} {_name}', f"dcat {user_id} {msg_id} {_name.replace(' ', '_')}")
    buttons.ibutton('Upload in All', f'dcat {user_id} {msg_id} All', 'header')
    buttons.ibutton('Cancel', f'dcat {user_id} {msg_id} dcancel', 'footer')
    buttons.ibutton(f'Done ({get_readable_time(60 - (time() - bot_cache[msg_id][3]))})', f'dcat {user_id} {msg_id} ddone', 'footer')
    await editMessage(query.message, f"<b>Select the category where you want to upload</b>\n\n<i><b>Upload Category:</b></i> <code>{cat_name}</code>\n\n<b>Timeout:</b> 60 sec", buttons.build_menu(3))


bot.add_handler(CallbackQueryHandler(confirm_dump, filters=regex("^dcat")))
