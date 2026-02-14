import os
import logging
import yt_dlp
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
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
PORT = int(os.getenv("PORT", 8000))

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

# مسار الكوكيز
COOKIES_FILE = "/app/cookies.txt"


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info(f"✅ Health check on port {PORT}")
    server.serve_forever()


def is_supported(url):
    return any(p in url.lower() for p in SUPPORTED)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 مرحباً! أنا بوت تحميل الميديا\n\n"
        "📥 أرسل رابط من أي منصة:\n"
        "▶️ YouTube | 🐦 Twitter/X\n"
        "📸 Instagram (فيديو + صور)\n"
        "📘 Facebook | 🎵 TikTok\n"
        "🔴 Reddit | 📌 Pinterest\n"
        "🎬 Vimeo | 🎵 SoundCloud\n\n"
        "✅ أرسل الرابط فقط!"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 طريقة الاستخدام:\n\n"
        "1️⃣ انسخ رابط الفيديو أو الصورة\n"
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
        # --- إعدادات التحميل ---
        opts = {
            'outtmpl': '/tmp/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 5,
            'extractor_retries': 3,
            'file_access_retries': 3,
            'no_check_certificates': True,
        }

        # --- إضافة الكوكيز إذا موجودة ---
        if os.path.exists(COOKIES_FILE):
            opts['cookiefile'] = COOKIES_FILE
            logger.info("Using cookies file")

        # --- تحديد نوع المحتوى ---
        is_instagram_post = "instagram.com/p/" in url
        is_photo_platform = any(p in url for p in [
            "instagram.com/p/", "pinterest.com"
        ])

        if is_photo_platform and not is_instagram_post:
            # صور
            opts['format'] = 'best'
        else:
            # فيديو
            opts['format'] = 'best[filesize<50M]/best'
            opts['merge_output_format'] = 'mp4'

        # --- التحميل ---
        with yt_dlp.YoutubeDL(opts) as ydl:
            logger.info(f"Downloading: {url}")
            info = ydl.extract_info(url, download=True)

            # التعامل مع البوستات المتعددة (carousel)
            entries = info.get('entries', [info])
            if not isinstance(entries, list):
                entries = list(entries)

        title = info.get('title', 'ميديا')
        sent_count = 0

        await msg.edit_text(f"📤 جاري الإرسال... ({len(entries)} ملف)")

        for i, entry in enumerate(entries):
            try:
                if entry is None:
                    continue

                # تحديد مسار الملف
                entry_id = entry.get('id', info.get('id', 'unknown'))
                entry_ext = entry.get('ext', 'mp4')
                path = f"/tmp/{entry_id}.{entry_ext}"

                # البحث عن الملف
                if not os.path.exists(path):
                    # جرب امتدادات ثانية
                    for ext in ['mp4', 'jpg', 'jpeg', 'png', 'webp']:
                        alt_path = f"/tmp/{entry_id}.{ext}"
                        if os.path.exists(alt_path):
                            path = alt_path
                            break

                if not os.path.exists(path):
                    logger.warning(f"File not found: {path}")
                    continue

                size = os.path.getsize(path)

                if size > 50 * 1024 * 1024:
                    os.remove(path)
                    await update.message.reply_text(
                        f"❌ الملف {i+1} أكبر من 50MB"
                    )
                    continue

                # --- تحديد النوع وإرسال ---
                ext = path.rsplit('.', 1)[-1].lower()

                with open(path, 'rb') as f:
                    if ext in ['jpg', 'jpeg', 'png', 'webp']:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"📸 {title}" if i == 0 else None
                        )
                    elif ext in ['mp3', 'ogg', 'wav', 'm4a']:
                        await update.message.reply_audio(
                            audio=f,
                            caption=f"🎵 {title}"
                        )
                    else:
                        await update.message.reply_video(
                            video=f,
                            caption=f"🎬 {title}" if i == 0 else None,
                            supports_streaming=True
                        )

                os.remove(path)
                sent_count += 1

            except Exception as e:
                logger.error(f"Error sending file {i}: {e}")
                continue

        if sent_count > 0:
            await msg.delete()
            logger.info(f"Sent {sent_count} files: {title}")
        else:
            await msg.edit_text("❌ لم أتمكن من إرسال أي ملف")

    except yt_dlp.utils.DownloadError as e:
        error = str(e)
        if "private" in error.lower():
            await msg.edit_text("🔒 المحتوى خاص")
        elif "unavailable" in error.lower():
            await msg.edit_text("❌ المحتوى غير متاح")
        elif "inappropriate" in error.lower():
            await msg.edit_text("🔞 المحتوى مقيد")
        elif "Sign in" in error or "bot" in error.lower():
            await msg.edit_text(
                "🤖 YouTube يطلب تأكيد هوية\n"
                "جاري المحاولة بطريقة ثانية..."
            )
            # محاولة ثانية بدون كوكيز
            await retry_download(update, msg, url)
        else:
            await msg.edit_text(f"❌ خطأ: {error[:200]}")
        logger.error(f"DL error: {error}")

    except Exception as e:
        await msg.edit_text(f"❌ خطأ: {str(e)[:200]}")
        logger.error(f"Error: {str(e)}")


async def retry_download(update, msg, url):
    """محاولة ثانية بإعدادات مختلفة"""
    try:
        opts = {
            'format': 'worst[ext=mp4]/worst',
            'outtmpl': '/tmp/retry_%(id)s.%(ext)s',
            'quiet': True,
            'no_check_certificates': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
        }

        if os.path.exists(COOKIES_FILE):
            opts['cookiefile'] = COOKIES_FILE

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)

        title = info.get('title', 'فيديو')

        with open(path, 'rb') as f:
            await update.message.reply_video(
                video=f,
                caption=f"🎬 {title} (جودة منخفضة)",
                supports_streaming=True
            )

        os.remove(path)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ فشلت المحاولة الثانية: {str(e)[:150]}")


def main():
    if not TOKEN:
        logger.error("❌ BOT_TOKEN مفقود!")
        return

    health_thread = Thread(target=start_health_server, daemon=True)
    health_thread.start()

    logger.info("🚀 البوت يعمل!")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, download
    ))

    logger.info("✅ جاهز!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
