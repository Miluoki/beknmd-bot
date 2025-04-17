import os
import json
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, BotCommand
from aiogram.utils import executor
import aiohttp
from gtts import gTTS
from tempfile import NamedTemporaryFile

# === Настройки ===
API_TOKEN = os.getenv("TG_API")
OPENROUTER_API_KEY = os.getenv("OPENROUTER")
ELEVENLABS_KEY = os.getenv("ELEVEN_KEY")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# === Переменные пользователей ===
user_prefs_file = "user_prefs.json"
user_prefs = {}
user_context = {}

# === Голоса ===
voices = {
    "Sargazy": "EXAVITQu4vr4xnSDxMaL",
    "Kanykey": "21m00Tcm4TlvDq8ikWAM",
    "Almambet": "AZnzlk1XvdvUeBnXmlld"
}

# === Загрузка настроек ===
def load_prefs():
    global user_prefs
    if os.path.exists(user_prefs_file):
        with open(user_prefs_file, "r") as f:
            user_prefs = json.load(f)

def save_prefs():
    with open(user_prefs_file, "w") as f:
        json.dump(user_prefs, f)

load_prefs()

# === AI Response ===
async def get_ai_response(prompt: str, user_id: int) -> str:
    prefs = user_prefs.get(str(user_id), {})
    lang = prefs.get("language", "en")
    mode = prefs.get("mode", "wise")
    history = user_context.get(user_id, [])[-5:]
    messages = [{"role": "system", "content": f"You are a {mode} character who replies in {lang}"}] + history + [{"role": "user", "content": prompt}]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"model": "openchat/openchat-3.5-0106", "messages": messages}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                answer = data["choices"][0]["message"]["content"]
                user_context.setdefault(user_id, []).append({"role": "user", "content": prompt})
                user_context[user_id].append({"role": "assistant", "content": answer})
                return answer
            else:
                return translate("AI is temporarily unavailable.", lang)

# === Перевод ===
def translate(text, lang):
    tr = {
        "AI is temporarily unavailable.": {
            "ru": "ИИ временно недоступен.",
            "es": "La IA está temporalmente no disponible."
        },
        "Voice limit reached.": {
            "ru": "Лимит голосов исчерпан.",
            "es": "Límite de voz alcanzado."
        }
    }
    return tr.get(text, {}).get(lang, text)

# === Голосовой ответ ===
async def speak(text: str, user_id: int) -> str:
    prefs = user_prefs.get(str(user_id), {})
    voice = prefs.get("voice", "Sargazy")
    lang = prefs.get("language", "en")

    headers = {
        "xi-api-key": ELEVENLABS_KEY,
        "Content-Type": "application/json"
    }
    if len(text) > 900:
        text = text[:900]

    json_data = {
        "text": text,
        "voice_settings": {"stability": 0.3, "similarity_boost": 0.8},
        "model_id": "eleven_multilingual_v2"
    }

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voices.get(voice)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=json_data) as resp:
                if resp.status == 429:
                    return "📛 Голосовые временно отключены — лимит исчерпан."
                if resp.status != 200:
                    raise Exception("Eleven failed")
                data = await resp.read()
                with NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                    f.write(data)
                    return f.name
    except:
        tts = gTTS(text=text, lang=lang)
        fallback = NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(fallback.name)
        return fallback.name

# === Команды ===
@dp.message_handler(commands=["start"])
async def start(message: Message):
    user_id = str(message.from_user.id)
    if user_id not in user_prefs:
        user_prefs[user_id] = {"language": "en", "mode": "wise", "voice": "Sargazy"}
        save_prefs()
    await message.answer("👋 Welcome to BEKNMD — digital nomad is online. Type /help")

@dp.message_handler(commands=["help"])
async def help_cmd(msg: Message):
    await msg.answer("""🤖 Available Commands:
/start — Wake up the bot
/help — Show help
/talk — Chat with BEKNMD
/ask <question>
/meme — Get a meme
/wisdom — Quote
/mode — Vibe
/language — Language
/voice — Voice style
/speak — Voice reply
/time — Server time""")

@dp.message_handler(commands=["language"])
async def set_lang(msg: Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("English", "Русский", "Español")
    await msg.answer("🌐 Choose language:", reply_markup=kb)

@dp.message_handler(lambda msg: msg.text in ["English", "Русский", "Español"])
async def lang_chosen(msg: Message):
    uid = str(msg.from_user.id)
    lang = {"English": "en", "Русский": "ru", "Español": "es"}[msg.text]
    user_prefs[uid]["language"] = lang
    save_prefs()
    await msg.answer(f"✅ Language set to {msg.text}", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(commands=["mode"])
async def set_mode_cmd(msg: Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("wise", "meme", "smart")
    await msg.answer("🎭 Choose vibe:", reply_markup=kb)

@dp.message_handler(lambda msg: msg.text in ["wise", "meme", "smart"])
async def vibe_mode(msg: Message):
    uid = str(msg.from_user.id)
    user_prefs[uid]["mode"] = msg.text
    save_prefs()
    await msg.answer(f"✅ Vibe set to {msg.text}", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(commands=["voice"])
async def voice_choice(msg: Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Sargazy", "Kanykey", "Almambet")
    await msg.answer("🗣 Choose voice:", reply_markup=kb)

@dp.message_handler(lambda msg: msg.text in ["Sargazy", "Kanykey", "Almambet"])
async def set_voice(msg: Message):
    uid = str(msg.from_user.id)
    user_prefs[uid]["voice"] = msg.text
    save_prefs()
    await msg.answer(f"✅ Voice set to {msg.text}", reply_markup=types.ReplyKeyboardRemove())

@dp.message_handler(commands=["ask"])
async def ask_cmd(msg: Message):
    prompt = msg.get_args()
    if not prompt:
        await msg.answer("❓ Use like this: /ask What is the meaning of life?")
        return
    reply = await get_ai_response(prompt, msg.from_user.id)
    await msg.answer(reply)

@dp.message_handler(commands=["speak"])
async def speak_cmd(msg: Message):
    uid = msg.from_user.id
    ctx = user_context.get(uid, [])
    if not ctx:
        await msg.answer("🛑 Nothing to speak yet. Use /ask first.")
        return
    text = ctx[-1]["content"]
    audio = await speak(text, uid)
    await msg.answer_voice(types.InputFile(audio))

@dp.message_handler(commands=["talk"])
async def talk_cmd(msg: Message):
    await msg.answer("🧠 I'm BEKNMD. Use /ask <question> or /speak to hear my voice.")

@dp.message_handler(commands=["meme"])
async def meme(msg: Message):
    await msg.answer("🧠 Meme of the day: 'Buy high, sell never.'")

@dp.message_handler(commands=["wisdom"])
async def wisdom(msg: Message):
    await msg.answer("📜 Wisdom: 'In crypto, silence is a bullish signal.'")

@dp.message_handler(commands=["time"])
async def time_cmd(msg: Message):
    await msg.answer("⏰ Server time: " + datetime.now().strftime("%H:%M:%S — %d.%m.%Y"))

@dp.message_handler()
async def fallback(msg: Message):
    await msg.answer("⚠️ Unknown command. Type /help")

# === Установка меню ===
async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand("start", "Launch the nomad's world"),
        BotCommand("help", "Show help menu"),
        BotCommand("meme", "Get a meme from BEKNMD"),
        BotCommand("wisdom", "Receive a philosophical quote"),
        BotCommand("talk", "Talk with the nomad AI"),
        BotCommand("ask", "Ask anything to BEKNMD"),
        BotCommand("language", "Change the bot's language"),
        BotCommand("mode", "Switch vibe: meme, wise, smart"),
        BotCommand("voice", "Choose your narrator voice"),
        BotCommand("speak", "Speak out a message"),
        BotCommand("time", "Get server time")
    ])

# === Запуск ===
if __name__ == '__main__':
    async def main():
        try:
            await set_commands(bot)
        except Exception as e:
            print("⚠️ Menu not updated:", e)
        await dp.start_polling()
    asyncio.run(main())
