import os
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
app = FastAPI(title="ZERO BOT")

NETWORKS = {
    "djezzy": {
        "name": "🔴 Djezzy",
        "note": "لعروض جازي، تحقق من تطبيق Djezzy أو الموقع الرسمي. قد تختلف العروض حسب الشريحة والاشتراك.",
        "url": "https://www.djezzy.dz/"
    },
    "ooredoo": {
        "name": "🔴 Ooredoo",
        "note": "لعروض أوريدو، تحقق من تطبيق My Ooredoo أو الموقع الرسمي. قد تختلف العروض حسب الشريحة والاشتراك.",
        "url": "https://www.ooredoo.dz/"
    },
    "mobilis": {
        "name": "🟢 Mobilis",
        "note": "لعروض موبيليس، تحقق من الموقع أو تطبيقات موبيليس الرسمية. قد تختلف العروض حسب الشريحة والاشتراك.",
        "url": "https://mobilis.dz/"
    }
}

def keyboard(rows):
    return {"inline_keyboard": [[{"text": label, "callback_data": data}] for label, data in rows]}

MAIN_ROWS = [
    ("🔴 عروض Djezzy", "net:djezzy"),
    ("🔴 عروض Ooredoo", "net:ooredoo"),
    ("🟢 عروض Mobilis", "net:mobilis"),
    ("🎁 العروض المجانية", "free"),
    ("📶 جميع الشبكات", "all"),
    ("ℹ️ المساعدة", "help"),
]

async def tg(method: str, payload: dict):
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f"{API}/{method}", json=payload)
        data = response.json()
        if not response.is_success or not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")
        return data["result"]

async def send_message(chat_id: int, text: str, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await tg("sendMessage", payload)

async def answer_callback(callback_id: str, text: str = ""):
    await tg("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})

async def show_menu(chat_id: int):
    await send_message(
        chat_id,
        "👑 ZERO BOT 🇩🇿\n\nمرحباً بك!\nاختر شبكة الاتصالات أو نوع العروض الذي تريد استكشافه.\n\nتنبيه: نعرض معلومات وروابط رسمية؛ لا نضمن وجود عرض مجاني لكل رقم.",
        keyboard(MAIN_ROWS)
    )

async def show_network(chat_id: int, key: str):
    item = NETWORKS[key]
    rows = [
        ("🌐 الموقع الرسمي", f"url:{key}"),
        ("⬅️ القائمة الرئيسية", "menu"),
    ]
    await send_message(
        chat_id,
        f"{item['name']}\n\n{item['note']}\n\nلا تدخل كلمة مرورك أو رمز SMS في البوت. استخدم التطبيق أو الموقع الرسمي للمتعامل للتحقق من أهليتك وتأكيد أي تفعيل.",
        keyboard(rows)
    )

@app.get("/", response_class=PlainTextResponse)
async def health():
    return "ZERO BOT is running"

@app.on_event("startup")
async def register_webhook():
    if not PUBLIC_URL:
        return
    payload = {"url": f"{PUBLIC_URL}/telegram/{WEBHOOK_SECRET}"}
    await tg("setWebhook", payload)

@app.post("/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    update = await request.json()

    message = update.get("message")
    if message:
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip().lower()
        if text in ("/start", "start", "/menu", "menu"):
            await show_menu(chat_id)
        elif text in ("/help", "help"):
            await send_message(chat_id, "استخدم /start لفتح القائمة. اختر الشبكة، ثم اتبع الروابط الرسمية للتحقق من العروض.")
        else:
            await send_message(chat_id, "لم أفهم طلبك. أرسل /start لعرض القائمة الرئيسية.")
        return {"ok": True}

    callback = update.get("callback_query")
    if callback:
        chat_id = callback["message"]["chat"]["id"]
        data = callback.get("data", "")
        await answer_callback(callback["id"])
        if data == "menu":
            await show_menu(chat_id)
        elif data.startswith("net:"):
            key = data.split(":", 1)[1]
            if key in NETWORKS:
                await show_network(chat_id, key)
        elif data == "free":
            await send_message(
                chat_id,
                "🎁 العروض المجانية\n\nلا توجد قاعدة موثوقة تسمح لنا بتأكيد عرض مجاني لكل الأرقام تلقائياً حالياً. افتح شبكة هاتفك من القائمة للتحقق من العروض الرسمية المتاحة لرقمك. سنضيف العروض المؤكدة بعد التحقق من مصدرها وشروطها.",
                keyboard([("🔴 Djezzy", "net:djezzy"), ("🔴 Ooredoo", "net:ooredoo"), ("🟢 Mobilis", "net:mobilis"), ("⬅️ القائمة الرئيسية", "menu")])
            )
        elif data == "all":
            await send_message(chat_id, "📶 اختر الشبكة لعرض روابطها ومعلومات التحقق الرسمية.", keyboard(MAIN_ROWS[:3] + [("⬅️ القائمة الرئيسية", "menu")]))
        elif data == "help":
            await send_message(chat_id, "ℹ️ المساعدة\n\n1) اختر المتعامل.\n2) افتح المصدر الرسمي.\n3) تحقق من صلاحية العرض لرقمك.\n4) أكّد التفعيل بنفسك لدى المتعامل.\n\nلا ترسل رموز SMS أو كلمات المرور إلى ZERO BOT.", keyboard([("⬅️ القائمة الرئيسية", "menu")]))
        elif data.startswith("url:"):
            key = data.split(":", 1)[1]
            if key in NETWORKS:
                await send_message(chat_id, f"الرابط الرسمي: {NETWORKS[key]['url']}")
        return {"ok": True}

    return {"ok": True}
