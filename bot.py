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

# Temporary storage for user images in memory
user_images = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message."""
    await update.message.reply_text(
        "👋 Welcome! Send me any image (as a photo or document), and I will offer options to convert it to another format."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles uploaded photos/images."""
    user_id = update.effective_user.id
    
    # Get the highest resolution photo version
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and update.message.document.mime_type.startswith("image/"):
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("Please send a valid image file.")
        return

    # Download file bytes
    file = await context.bot.get_file(file_id)
    image_bytes = await file.download_as_bytearray()
    
    # Store in memory for this user
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
    """Processes callback query buttons to convert image."""
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
        # Load image with Pillow
        raw_bytes = user_images[user_id]
        img = Image.open(io.BytesIO(raw_bytes))

        # Handle RGBA/transparency issues when converting to JPEG/PDF
        if target_format in ["JPEG", "PDF"] and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Save converted output in memory stream
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

        # Send converted document/image back to user
        await context.bot.send_document(
            chat_id=user_id,
            document=output_stream,
            caption=f"✅ Converted successfully to {target_format}!",
        )

        # Cleanup memory buffer for user
        del user_images[user_id]

    except Exception as e:
        logging.error(f"Error during conversion: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ An error occurred while processing the image format.",
        )

def main():
    # Fetch token from environment variables
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN environment variable is missing!")

    app = ApplicationBuilder().token(token).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_conversion, pattern="^convert_"))

    # Start Polling
    app.run_polling()

if __name__ == "__main__":
    main()