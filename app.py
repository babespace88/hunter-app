import os
import tempfile
import requests
import fal_client
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
FAL_KEY = os.environ.get("FAL_KEY")

user_usage = {}
VIDEO_LIMIT = 50

def get_usage(user_id):
    if user_id not in user_usage:
        user_usage[user_id] = {"video": 0}
    return user_usage[user_id]

def check_limit(user_id):
    return get_usage(user_id)["video"] < VIDEO_LIMIT

def increment_usage(user_id):
    get_usage(user_id)
    user_usage[user_id]["video"] += 1

# ─── Upload gambar ke fal ───
async def upload_image_to_fal(update: Update, context):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    response = requests.get(file.file_path)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name

    image_url = fal_client.upload_file(tmp_path)
    os.remove(tmp_path)
    print("Uploaded URL:", image_url)
    return image_url

# ─── Generate Video ───
def generate_video(prompt, image_url):
    def on_queue_update(update):
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                print(log["message"])

    result = fal_client.subscribe(
        "bytedance/seedance-2.0/fast/image-to-video",
        arguments={
            "prompt": prompt,
            "image_url": image_url
        },
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    return result

# ─── Handler /start ───
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Video Bot*\n\n"
        "Hantar gambar dengan caption sebagai prompt!\n\n"
        "Contoh:\n"
        "• Hantar gambar + caption `she waves slowly`\n"
        "• Hantar gambar + caption `the cat jumps off the table`\n"
        "• Hantar gambar + caption `camera pulls back, cinematic`\n\n"
        "📊 Semak usage: /usage",
        parse_mode="Markdown"
    )

# ─── Handler /usage ───
async def usage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = get_usage(user_id)
    await update.message.reply_text(
        f"📊 *Usage Awak:*\n\n"
        f"🎬 Video: {u['video']}/{VIDEO_LIMIT}",
        parse_mode="Markdown"
    )

# ─── Handler gambar + caption ───
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    prompt = update.message.caption
    if not prompt:
        await update.message.reply_text(
            "⚠️ Sila hantar gambar dengan caption sebagai prompt!\n\n"
            "Contoh: hantar gambar + caption `she waves slowly`"
        )
        return

    if not check_limit(user_id):
        await update.message.reply_text(f"❌ Had video awak dah penuh! ({VIDEO_LIMIT} video)")
        return

    await update.message.reply_text("⏳ Sedang jana video... (1-3 minit)")

    try:
        # Upload gambar
        image_url = await upload_image_to_fal(update, context)

        # Terus generate video
        result = generate_video(prompt, image_url)
        print("Result:", result)

        video_url = result["video"]["url"]
        increment_usage(user_id)
        u = get_usage(user_id)

        await context.bot.send_video(
            chat_id=update.effective_chat.id,
            video=video_url,
            caption=f"🎬 {prompt}\n\n🎬 {u['video']}/{VIDEO_LIMIT}"
        )

    except Exception as e:
        print("Error:", e)
        await update.message.reply_text(f"❌ Gagal jana video.\n\nError: {e}")

# ─── Handler teks biasa ───
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 Hantar gambar dengan caption untuk jana video!\n\n"
        "Contoh: hantar gambar + caption `she walks in the rain`"
    )

# ─── Run Bot ───
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("usage", usage))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("Video Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
