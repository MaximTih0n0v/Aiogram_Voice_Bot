import aiofiles
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import os
import uuid
from aiohttp import web, ClientSession
from aiogram.client.bot import DefaultBotProperties
import tempfile
from config import settings
from pathlib import Path
from openai import AsyncOpenAI, OpenAI
import asyncio


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

client = OpenAI(api_key=OPENAI_API_KEY)


async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook set to {WEBHOOK_URL}")
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
        assistant = await client.beta.assistants.create(
            name="Personal assistant",
            instructions="You are a personal assistant who helps with any issue.",
            tools=[{"type": "code_interpreter"}],
            model="gpt-4o"
        )

        thread = await client.beta.threads.create()

        message = await client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=prompt
        )

        run = await client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )

        while True:
            messages = await client.beta.threads.messages.list(thread_id=thread.id)
            assistant_message = None

            async for msg in messages:
                if msg.role == 'assistant':
                    assistant_message = msg

            if assistant_message:
                if assistant_message.content:
                    text_content = assistant_message.content[0]
                    if hasattr(text_content, 'text'):
                        response_text = text_content.text.value
                        print(response_text)
                        return response_text

            await asyncio.sleep(1)

    except Exception as e:
        print(f"Failed to get OpenAI response: {e}")
        return "Не удалось получить ответ от OpenAI."


async def synthesize_speech(text):
    try:
        temp_audio_file = Path(tempfile.gettempdir()) / f"{uuid.uuid4().hex}.mp3"

        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text
        )

        response.stream_to_file(temp_audio_file)

        return str(temp_audio_file)
    except Exception as e:
        print(f"Не удалось получить ответ от OpenAI TTS: {e}")
        return None


async def transcribe_audio_with_openai(file_path):
    try:
        with open(file_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text"
            )
            return transcription
    except Exception as e:
        print(f"Ошибка при расшифровке аудио через OpenAI: {e}")
        return None


async def handle_voice_message(message: Message):
    file_id = message.voice.file_id
    chat_id = message.chat.id
    filename = uuid.uuid4().hex

    file_path = await download_file(file_id, filename)
    if file_path:

        transcribed_text = await transcribe_audio_with_openai(file_path)

        if transcribed_text:
            await bot.send_message(chat_id, f"Распознанный текст: {transcribed_text}")
            print(transcribed_text)

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
