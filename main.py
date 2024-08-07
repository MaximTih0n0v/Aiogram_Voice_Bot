import aiofiles
import whisper
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import os
import uuid
from aiohttp import web, ClientSession
from aiogram.client.bot import DefaultBotProperties
import tempfile
from config import settings
from openai import AsyncOpenAI


TG_API = settings.TG_API
WEBHOOK_HOST = settings.WEBHOOK_HOST
WEBHOOK_PATH = settings.WEBHOOK_PATH
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST = settings.WEBAPP_HOST
WEBAPP_PORT = settings.WEBAPP_PORT

OPENAI_API_KEY = settings.OPENAI_API_KEY
OPENAI_TTS_URL = settings.OPENAI_TTS_URL

bot = Bot(token=TG_API, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

model = whisper.load_model('small')


async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    print("Bot started")


async def on_shutdown(app):
    await bot.delete_webhook()


async def download_file(file_id, filename):
    async with ClientSession() as session:
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path
        ext = file_path.split('.')[-1]

        file_url = f'https://api.telegram.org/file/bot{TG_API}/{file_path}'
        async with session.get(file_url) as response:
            if response.status == 200:
                async with aiofiles.open(f'{filename}.{ext}', mode='wb') as f:
                    content = await response.read()
                    await f.write(content)
                    return f'{filename}.{ext}'
            else:
                print(f"Failed to download file: {response.status}")
                return None


async def get_openai_response(prompt):
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Failed to get OpenAI response: {e}")
        return "Не удалось получить ответ от OpenAI."


async def synthesize_speech(text):
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "tts-1",
        "input": text,
        "voice": "nova",
        "response_format": "mp3",
        "speed": 1.0
    }

    async with ClientSession() as session:
        async with session.post(OPENAI_TTS_URL, headers=headers, json=data) as response:
            if response.status == 200:
                audio_content = await response.read()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio_file:
                    temp_audio_file.write(audio_content)
                    return temp_audio_file.name
            else:
                error_message = await response.text()
                print(f"Не удалось получить ответ от OpenAI TTS: {response.status}, {error_message}")
                return None


async def handle_voice_message(message: Message):
    file_id = message.voice.file_id
    chat_id = message.chat.id
    filename = uuid.uuid4().hex

    file_path = await download_file(file_id, filename)
    if file_path:
        result = model.transcribe(file_path, fp16=False)
        transcribed_text = result.get('text', '').strip()

        if transcribed_text:
            await bot.send_message(chat_id, f"Распознанный текст: {transcribed_text}")
            print(transcribed_text)

            # Получаем ответ от OpenAI
            response = await get_openai_response(transcribed_text)
            await bot.send_message(chat_id, response)
            print(f"Ответ от OpenAI: {response}")

            audio_file_path = await synthesize_speech(response)
            if audio_file_path:
                audio_file = FSInputFile(audio_file_path)
                await bot.send_voice(chat_id, audio_file)
                os.remove(audio_file_path)
        else:
            await bot.send_message(chat_id, "Не удалось распознать текст!")
            print("Не удалось распознать текст!")

        os.remove(file_path)


dp.message.register(handle_voice_message, F.voice)

if __name__ == "__main__":
    app = web.Application()
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
