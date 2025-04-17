# BEKNMD SYSTEM V2 — ФИНАЛЬНЫЙ КОМБИНИРОВАННЫЙ ФАЙЛ
# Команды: /start /help /ask /speak /voice_on /voice_off /language /mode /voice /meme /wisdom /time

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
ADMIN_ID = 863267227

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_prefs_file = "user_prefs.json"
user_prefs = {}
user_context = {}

voices = {
    "Sargazy": "EXAVITQu4vr4xnSDxMaL",
    "Kanykey": "21m00Tcm4TlvDq8ikWAM",
    "Almambet": "AZnzlk1XvdvUeBnXmlld"
}

def load_prefs():
    global user_prefs
    if os.path.exists(user_prefs_file):
        with open(user_prefs_file, "r") as f:
            user_prefs = json.load(f)

def save_prefs():
    with open(user_prefs_file, "w") as f:
        json.dump(user_prefs, f)

load_prefs()

def init_user(uid):
    if uid not in user_prefs:
        user_prefs[uid] = {"language": "en", "mode": "wise", "voice": "Sargazy", "voice_mode": False}

async def get_ai_response(prompt: str, user_id: int) -> str:
    prefs = user_prefs.get(str(user_id), {})
    lang = prefs.get("language", "en")
    mode = prefs.get("mode", "wise")
    history = user_context.get(user_id, [])[-5:]
    messages = [{"role": "system", "content": f"You are a {mode} character who replies in {lang}"}] + history + [{"role": "user", "content": prompt}]

    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
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

async def speak(text: str, user_id: int) -> str:
    prefs = user_prefs.get(str(user_id), {})
    voice = prefs.get("voice", "Sargazy")
    lang = prefs.get("language", "en")
    headers = {"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"}
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
                    return "📛 ElevenLabs limit reached."
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

def translate(text, lang):
    tr = {
        "AI is temporarily unavailable.": {"ru": "ИИ временно недоступен.", "es": "La IA está temporalmente no disponible."},
        "Voice limit reached.": {"ru": "Лимит голосов исчерпан.", "es": "Límite de voz alcanzado."}
    }
    return tr.get(text, {}).get(lang, text)

@dp.message_handler(commands=["start"])
async def start(message: Message):
    uid = str(message.from_user.id)
    init_user(uid)
    await message.answer("👋 Welcome to BEKNMD — digital nomad is online. Type /help")

@dp.message_handler(commands=["help"])
async def help_cmd(msg: Message):
    await msg.answer("""🤖 Available Commands:
/start /help /ask /speak
/voice_on /voice_off
/language /mode /voice
/wisdom /meme /time""")

@dp.message_handler(commands=["voice_on"])
async def voice_on(msg: Message):
    uid = str(msg.from_user.id)
    init_user(uid)
    user_prefs[uid]["voice_mode"] = True
    save_prefs()
    await msg.answer("🔊 Voice mode: ON")

@dp.message_handler(commands=["voice_off"])
async def voice_off(msg: Message):
    uid = str(msg.from_user.id)
    init_user(uid)
    user_prefs[uid]["voice_mode"] = False
    save_prefs()
    await msg.answer("🔇 Voice mode: OFF")

@dp.message_handler(commands=["ask"])
async def ask_cmd(msg: Message):
    uid = str(msg.from_user.id)
    init_user(uid)
    prompt = msg.get_args()
    if not prompt:
        await msg.answer("❓ Use like this: /ask What is the meaning of life?")
        return
    reply = await get_ai_response(prompt, uid)
    await msg.answer(reply)
    if user_prefs[uid].get("voice_mode"):
        audio = await speak(reply, uid)
        await msg.answer_voice(types.InputFile(audio))

@dp.message_handler(commands=["speak"])
async def speak_cmd(msg: Message):
    uid = str(msg.from_user.id)
    init_user(uid)
    ctx = user_context.get(uid, [])
    if not ctx:
        await msg.answer("🛑 Nothing to speak yet. Use /ask first.")
        return
    text = ctx[-1]["content"]
    audio = await speak(text, uid)
    await msg.answer_voice(types.InputFile(audio))

@dp.message_handler(commands=["language"])
async def set_lang(msg: Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("English", "Русский", "Español")
    await msg.answer("🌐 Choose language:", reply_markup=kb)

@dp.message_handler(lambda msg: msg.text in ["English", "Русский", "Español"])
async def lang_chosen(msg: Message):
    uid = str(msg.from_user.id)
    init_user(uid)
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
    init_user(uid)
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
    init_user(uid)
    user_prefs[uid]["voice"] = msg.text
    save_prefs()
    await msg.answer(f"✅ Voice set to {msg.text}", reply_markup=types.ReplyKeyboardRemove())

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

async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand("start", "Launch the nomad's world"),
        BotCommand("help", "Show help menu"),
        BotCommand("ask", "Ask anything to BEKNMD"),
        BotCommand("speak", "Voice reply"),
        BotCommand("voice_on", "Enable auto speech"),
        BotCommand("voice_off", "Disable auto speech"),
        BotCommand("language", "Change language"),
        BotCommand("mode", "Change vibe mode"),
        BotCommand("voice", "Choose voice"),
        BotCommand("meme", "Get a meme"),
        BotCommand("wisdom", "Drop wisdom"),
        BotCommand("time", "Check server time")
    ])

if __name__ == '__main__':
    async def main():
        try:
            await set_commands(bot)
        except Exception as e:
            print("⚠️ Menu not updated:", e)
        await dp.start_polling()
    asyncio.run(main())
