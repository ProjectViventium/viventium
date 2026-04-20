import config

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from md2tgmd.src.md2tgmd import escape

# REMOVED: i18n - Using hardcoded English strings for simplicity
from utils.scripts import GetMesageInfo

def ban_message(update, convo_id):
    message = (
        f"`Hi, {update.effective_user.username}!`\n\n"
        f"id: `{update.effective_user.id}`\n\n"
        f"You do not have permission to access!\n\n"
    )
    return escape(message, italic=False)

# Check if in whitelist
def Authorization(func):
    async def wrapper(*args, **kwargs):
        update, context = args[:2]
        _, _, _, chatid, _, _, _, message_thread_id, convo_id, _, _, _, _, _ = await GetMesageInfo(update, context, voice=False)
        if config.BLACK_LIST and chatid in config.BLACK_LIST:
            message = ban_message(update, convo_id)
            await context.bot.send_message(chat_id=chatid, message_thread_id=message_thread_id, text=message, parse_mode='MarkdownV2')
            return
        if config.whitelist == None or (config.GROUP_LIST and chatid in config.GROUP_LIST):
            return await func(*args, **kwargs)
        if config.whitelist and update.effective_user and str(update.effective_user.id) not in config.whitelist:
            message = ban_message(update, convo_id)
            await context.bot.send_message(chat_id=chatid, message_thread_id=message_thread_id, text=message, parse_mode='MarkdownV2')
            return
        return await func(*args, **kwargs)
    return wrapper

# Check if in group chat whitelist
def GroupAuthorization(func):
    async def wrapper(*args, **kwargs):
        update, context = args[:2]
        _, _, _, chatid, _, _, _, message_thread_id, convo_id, _, _, _, _, _ = await GetMesageInfo(update, context, voice=False)
        if config.GROUP_LIST == None:
            return await func(*args, **kwargs)
        if update.effective_chat == None or chatid[0] != "-":
            return await func(*args, **kwargs)
        if (chatid not in config.GROUP_LIST):
            if (config.ADMIN_LIST and str(update.effective_user.id) in config.ADMIN_LIST):
                return await func(*args, **kwargs)
            message = ban_message(update, convo_id)
            await context.bot.send_message(chat_id=chatid, message_thread_id=message_thread_id, text=message, parse_mode='MarkdownV2')
            return
        return await func(*args, **kwargs)
    return wrapper

# Check if is admin
def AdminAuthorization(func):
    async def wrapper(*args, **kwargs):
        update, context = args[:2]
        _, _, _, chatid, _, _, _, message_thread_id, convo_id, _, _, _, _, _ = await GetMesageInfo(update, context, voice=False)
        if config.ADMIN_LIST == None:
            return await func(*args, **kwargs)
        if (str(update.effective_user.id) not in config.ADMIN_LIST):
            message = ban_message(update, convo_id)
            await context.bot.send_message(chat_id=chatid, message_thread_id=message_thread_id, text=message, parse_mode='MarkdownV2')
            return
        return await func(*args, **kwargs)
    return wrapper

def APICheck(func):
    async def wrapper(*args, **kwargs):
        update, context = args[:2]
        _, _, _, chatid, _, _, _, message_thread_id, convo_id, _, _, _, _, _ = await GetMesageInfo(update, context, voice=False)
        from config import (
            Users,
            get_robot,
        )
        from md2tgmd.src.md2tgmd import escape
        robot, role, api_key, api_url = get_robot(convo_id)
        if robot == None:
            api_none_message = (
                "Please set the API key using the /start command, you can directly copy the following example:\n\n"
                "If you have an official OpenAI API key, please use the following command:\n\n"
                "`/start your_api_key`\n\n"
                "If you are using a third-party API key, please use the following command:\n\n"
                "`/start https://your_api_url your_api_key`"
            )
            await context.bot.send_message(
                chat_id=chatid,
                message_thread_id=message_thread_id,
                text=escape(api_none_message),
                parse_mode='MarkdownV2',
            )
            return
        if (api_key and api_key.endswith("your_api_key")) or (api_url and api_url.endswith("your_api_url")):
            api_error_message = (
                "The API key or API URL you entered is invalid, please reset the API key using the /start command, you can directly copy the following example:\n\n"
                "If you have an official OpenAI API key, please use the following command:\n\n"
                "`/start your_api_key`\n\n"
                "If you are using a third-party API key, please use the following command:\n\n"
                "`/start https://your_api_url your_api_key`"
            )
            await context.bot.send_message(chat_id=chatid, message_thread_id=message_thread_id, text=escape(api_error_message), parse_mode='MarkdownV2')
            return
        return await func(*args, **kwargs)
    return wrapper

# REMOVED: PrintMessage decorator - Debug-only, not needed in production
