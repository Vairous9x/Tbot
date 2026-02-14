import os
import logging
import yt_dlp
from telegram import Update
from telegram.ext import (
    Application, CommandHandler,
    MessageHandler, filters, ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

SUPPORTED = [
    "youtube.com", "youtu.be",
    "twitter.com", "x.com",
    "instagram.com",
    "facebook.com", "fb.watch",
    "tiktok.com", "reddit.com",
    "pinterest.com", "dailymotion.com",
    "vimeo.com", "soundcloud.com",
    "twitch.tv"
]


def is_supported(url):
    return any(p in url.lower() for p in SUPPORTED)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 مرحباً! أنا بوت تحميل الميديا\n\n"
        "📥 أرسل رابط من أي منصة:\n"
        "▶️ YouTube | 🐦 Twitter/X\n"
        "📸 Instagram | 📘 Facebook\n"
        "🎵 TikTok | 🔴 Reddit\n"
        "📌 Pinterest | 🎬 Vimeo\n"
        "🎵 SoundCloud | 🟣 Twitch\n\n"
        "✅ أرسل الرابط فقط!"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 طريقة الاستخدام:\n\n"
        "1️⃣ انسخ رابط الفيديو\n"
        "2️⃣ أرسله هنا\n"
        "3️⃣ انتظر التحميل\n\n"
        "/start - تشغيل البوت\n"
        "/help - المساعدة"
    )


async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ أرسل رابط صحيح يبدأ بـ http://")
        return

    if not is_supported(url):
        await update.message.reply_text("❌ المنصة غير مدعومة")
        return

    msg = await update.message.reply_text("⏳ جاري التحميل... انتظر")

    try:
        opts = {
            'format': 'best[filesize<50M]/best',
            'outtmpl': '/tmp/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'merge_output_format': 'mp4',
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            logger.info(f"Downloading: {url}")
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)

            if not path.endswith('.mp4'):
                mp4 = path.rsplit('.', 1)[0] + '.mp4'
                if os.path.exists(mp4):
                    path = mp4

        title = info.get('title', 'ميديا')
        size = os.path.getsize(path)

        logger.info(f"Downloaded: {title} ({size} bytes)")

        if size > 50 * 1024 * 1024:
            os.remove(path)
            await msg.edit_text("❌ الملف أكبر من 50MB (حد تيليجرام)")
            return

        await msg.edit_text("📤 جاري الإرسال...")

        with open(path, 'rb') as f:
            if info.get('vcodec') == 'none':
                await update.message.reply_audio(
                    audio=f,
                    caption=f"🎵 {title}"
                )
            else:
                await update.message.reply_video(
                    video=f,
                    caption=f"🎬 {title}",
                    supports_streaming=True
                )

        os.remove(path)
        await msg.delete()
        logger.info(f"Sent: {title}")

    except yt_dlp.utils.DownloadError as e:
        error = str(e)
        if "private" in error.lower():
            await msg.edit_text("🔒 المحتوى خاص")
        elif "unavailable" in error.lower():
            await msg.edit_text("❌ المحتوى غير متاح")
        else:
            await msg.edit_text(f"❌ خطأ: {error[:200]}")
        logger.error(f"DL error: {error}")

    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {str(e)[:200]}")
        logger.error(f"Error: {str(e)}")


def main():
    if not TOKEN:
        logger.error("❌ BOT_TOKEN مفقود!")
        return

    logger.info("🚀 البوت يعمل!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, download
    ))

    logger.info("✅ جاهز لاستقبال الرسائل!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
