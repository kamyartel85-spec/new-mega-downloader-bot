import os
import logging
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery

class MeganzClient(Client):
    def __init__(self):
        super().__init__(
            "MegaStreamSession",
            bot_token=os.getenv("BOT_TOKEN"),
            api_id=int(os.getenv("API_ID", 0)),
            api_hash=os.getenv("API_HASH", ""),
            plugins=dict(root="megadl/modules"),
        )
        self.glob_tmp = {}
        
        _auth_user = os.getenv("ALLOWED_USER_ID")
        self.auth_users = {int(_auth_user)} if _auth_user else set()

    def run_checks(self, func):
        async def cy_run(client: Client, msg):
            uid = msg.from_user.id
            if uid not in self.auth_users:
                text = "شما اجازه استفاده از این ربات شخصی را ندارید ✋"
                if isinstance(msg, Message):
                    await msg.reply(text)
                else:
                    await msg.message.edit_text(text)
                return
            try:
                return await func(client, msg)
            except Exception as e:
                text = f"خطای پیش‌بینی نشده: {e}"
                logging.error(text)
                if isinstance(msg, Message):
                    await msg.reply(text)
                else:
                    await msg.message.edit_text(text)
        return cy_run
