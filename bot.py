import io
import logging
import os
from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Logging configuration
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# Temporary in-memory buffer storage for uploaded user images
user_images = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a clear welcome message matching the ad copy."""
    await update.message.reply_text(
        "👋 Welcome to Fast Pic Converter Bot!\n\n"
        "Send me any photo or document image to convert it into PNG, JPG, WEBP, or PDF instantly."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends help instructions required for bot verification."""
    await update.message.reply_text(
        "ℹ️ <b>How to use this bot:</b>\n\n"
        "1. Upload an image as a photo or document.\n"
        "2. Choose your desired target format (PNG, JPG, WEBP, PDF).\n"
        "3. Download your converted file instantly!",
        parse_mode="HTML",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming photos and image documents."""
    user_id = update.effective_user.id

    # Retrieve file ID from photo or document
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("Please send a valid image file.")
        return

    # Download file into memory
    file = await context.bot.get_file(file_id)
    image_bytes = await file.download_as_bytearray()

    # Save to buffer
    user_images[user_id] = image_bytes

    # Inline options for conversion format
    keyboard = [
        [
            InlineKeyboardButton("PNG", callback_data="convert_PNG"),
            InlineKeyboardButton("JPG", callback_data="convert_JPEG"),
        ],
        [
            InlineKeyboardButton("WEBP", callback_data="convert_WEBP"),
            InlineKeyboardButton("PDF", callback_data="convert_PDF"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Choose the format you want to convert this image into:",
        reply_markup=reply_markup,
    )


async def handle_conversion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes inline button selection and returns converted image."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    target_format = query.data.split("_")[1]

    if user_id not in user_images:
        await query.edit_message_text(
            "⚠️ Image expired or not found. Please upload the photo again."
        )
        return

    await query.edit_message_text(f"⏳ Converting image to {target_format}...")

    try:
        # Load image via Pillow
        raw_bytes = user_images[user_id]
        img = Image.open(io.BytesIO(raw_bytes))

        # Convert RGBA/Palette modes to RGB for JPEG and PDF compatibility
        if target_format in ["JPEG", "PDF"] and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Save converted output to memory stream
        output_stream = io.BytesIO()
        file_ext = target_format.lower()

        if target_format == "JPEG":
            file_ext = "jpg"
            img.save(output_stream, format="JPEG", quality=95)
        elif target_format == "PDF":
            file_ext = "pdf"
            img.save(output_stream, format="PDF")
        else:
            img.save(output_stream, format=target_format)

        output_stream.seek(0)
        output_stream.name = f"converted_image.{file_ext}"

        # Send document back to user
        await context.bot.send_document(
            chat_id=user_id,
            document=output_stream,
            caption=f"✅ Converted successfully to {target_format}!",
        )

        # Clear buffer
        del user_images[user_id]

    except Exception as e:
        logging.error(f"Error during conversion: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ An error occurred while processing the image format.",
        )


def main():
    # Read environment variable token
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable is missing!")

    app = ApplicationBuilder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_conversion, pattern="^convert_"))

    # Start bot polling
    app.run_polling()


if __name__ == "__main__":
    main()
