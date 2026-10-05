import asyncio
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from megadl import CypherClient
from megadl.lib.megatools import MegaTools, StreamQueueFile, human_bytes

@CypherClient.on_message(filters.regex(r"https?:\/\/mega\.nz\/(file|#)?.+"))
@CypherClient.run_checks
async def dl_from(client: CypherClient, msg: Message):
    _mid = msg.id
    _usr = msg.from_user.id
    client.glob_tmp[_usr] = msg.text
    await msg.reply(
        "**یک عملیات انتخاب کنید:**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("دانلود و ارسال 📥📤", callback_data=f"dwn_mg-{_mid}")],
            [InlineKeyboardButton("لغو ❌", callback_data=f"cancelqcb-{_usr}")],
        ])
    )

@CypherClient.on_callback_query(filters.regex(r"cancelqcb?.+"))
@CypherClient.run_checks
async def cancel_cb(client, query: CallbackQuery):
    await query.message.delete()

@CypherClient.on_callback_query(filters.regex(r"dwn_mg?.+"))
@CypherClient.run_checks
async def dl_from_cb(client: CypherClient, query: CallbackQuery):
    _mid = int(query.data.split("-")[1])
    qcid = query.message.chat.id
    qusr = query.from_user.id
    url = client.glob_tmp.get(qusr)

    if not url:
        return await query.edit_message_text("❌ لینک یافت نشد. لطفا لینک را دوباره ارسال کنید.")

    await query.edit_message_text("`در حال بررسی فایل در سرور مگا 🔎...`")

    try:
        f_size, f_name, dl_url, tk, key = await MegaTools.get_download_info(url)
    except Exception as e:
        return await query.edit_message_text(f"`❌ خطا: {e}`")

    if f_size > 2000 * 1024 * 1024:
        return await query.edit_message_text(f"❌ حجم فایل ({human_bytes(f_size)}) بیشتر از 2GB است و توسط تلگرام پشتیبانی نمی‌شود.")

    await query.edit_message_text(f"`در حال استریم و آپلود فایل: {f_name} ({human_bytes(f_size)}) ⏳...`\n*(بدون اشغال حافظه دیسک)*")

    stream = StreamQueueFile(f_size, f_name)
    download_task = asyncio.create_task(MegaTools.stream_download(dl_url, f_size, tk, key, stream))

    try:
        await client.send_document(
            chat_id=qcid,
            document=stream,
            file_name=f_name,
            reply_to_message_id=_mid,
            caption=f"**فایل:** {f_name}\n**حجم:** {human_bytes(f_size)}\n✅ به صورت استریم دانلود و ارسال شد."
        )
        await query.edit_message_text("`✅ فایل با موفقیت استریم و ارسال شد!`")
    except Exception as e:
        await query.edit_message_text(f"`❌ خطا در ارسال فایل: {e}`")
    finally:
        stream.close()
        download_task.cancel()
        client.glob_tmp.pop(qusr, None)
