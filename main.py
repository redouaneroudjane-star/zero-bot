import os
import uuid
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"
app = FastAPI(title="ZERO BOT")

# Pending approvals are stored in memory. A restart clears pending items.
PENDING_OFFERS = {}

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

async def send_channel_message(text: str):
    if not CHANNEL_ID:
        raise RuntimeError("CHANNEL_ID is missing")
    await send_message(int(CHANNEL_ID), text)

async def show_menu(chat_id: int):
    await send_message(
        chat_id,
        "👑 ZERO BOT 🇩🇿\n\nمرحباً بك!\nاختر شبكة الاتصالات أو نوع العروض الذي تريد استكشافه.\n\nتنبيه: نعرض معلومات وروابط رسمية؛ لا نضمن وجود عرض مجاني لكل رقم.",
        keyboard(MAIN_ROWS)
    )

async def show_network(chat_id: int, key: str):
    item = NETWORKS[key]
    rows = [("🌐 الموقع الرسمي", f"url:{key}"), ("⬅️ القائمة الرئيسية", "menu")]
    await send_message(
        chat_id,
        f"{item['name']}\n\n{item['note']}\n\nلا تدخل كلمة مرورك أو رمز SMS في البوت. استخدم التطبيق أو الموقع الرسمي للمتعامل للتحقق من أهليتك وتأكيد أي تفعيل.",
        keyboard(rows)
    )

def is_admin(user_id: int) -> bool:
    return bool(ADMIN_CHAT_ID) and str(user_id) == ADMIN_CHAT_ID

@app.get("/", response_class=PlainTextResponse)
async def health():
    return "ZERO BOT is running"

@app.on_event("startup")
async def register_webhook():
    if PUBLIC_URL:
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
        user_id = message["from"]["id"]
        raw_text = (message.get("text") or "").strip()
        text = raw_text.lower()

        if text in ("/myid", "myid"):
            await send_message(chat_id, f"معرّف محادثتك (Chat ID): {chat_id}\nاحتفظ به ولا تنشره علناً.")
        elif text.startswith("/candidate"):
            if not is_admin(user_id) or chat_id != int(ADMIN_CHAT_ID):
                await send_message(chat_id, "هذا الأمر مخصص للمشرف فقط.")
            else:
                body = raw_text[len("/candidate"):].strip()
                if len(body) < 30 or ("http://" not in body and "https://" not in body):
                    await send_message(
                        chat_id,
                        "أرسل العرض بهذا الشكل:\n/candidate\nاسم العرض والشبكة\nالتفاصيل والسعر/الحجم والمدة\nالشروط والأهلية\nالمصدر الرسمي: https://...\nتاريخ الانتهاء أو غير محدد"
                    )
                else:
                    offer_id = uuid.uuid4().hex[:12]
                    PENDING_OFFERS[offer_id] = body
                    await send_message(
                        chat_id,
                        "📝 عرض بانتظار قرارك — لم يُنشر بعد:\n\n" + body,
                        {"inline_keyboard": [[
                            {"text": "✅ نشر في القناة", "callback_data": f"offer:publish:{offer_id}"},
                            {"text": "❌ رفض", "callback_data": f"offer:reject:{offer_id}"}
                        ]]}
                    )
        elif text in ("/test_channel", "test_channel"):
            if not CHANNEL_ID:
                await send_message(chat_id, "لم يتم ضبط CHANNEL_ID في إعدادات الاستضافة.")
            else:
                try:
                    member = await tg("getChatMember", {"chat_id": int(CHANNEL_ID), "user_id": user_id})
                    if member.get("status") not in ("creator", "administrator"):
                        await send_message(chat_id, "هذا الاختبار متاح لمسؤولي القناة فقط.")
                    else:
                        await send_channel_message("✅ ZERO BOT متصل بالقناة بنجاح! هذه رسالة اختبار.")
                        await send_message(chat_id, "✅ نجح الاختبار! تحقق من القناة.")
                except Exception:
                    await send_message(chat_id, "❌ تعذر النشر. تحقق من صلاحيات البوت ومعرّف القناة.")
        elif text in ("/start", "start", "/menu", "menu"):
            await show_menu(chat_id)
        elif text in ("/help", "help"):
            extra = "\nللمشرف: أرسل /candidate ثم تفاصيل العرض ومصدره لإرساله للمراجعة." if is_admin(user_id) else ""
            await send_message(chat_id, "استخدم /start لفتح القائمة. اختر الشبكة، ثم اتبع الروابط الرسمية للتحقق من العروض." + extra)
        else:
            await send_message(chat_id, "لم أفهم طلبك. أرسل /start لعرض القائمة الرئيسية.")
        return {"ok": True}

    callback = update.get("callback_query")
    if callback:
        data = callback.get("data", "")
        actor_id = callback.get("from", {}).get("id")
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        if data.startswith("offer:"):
            if not is_admin(actor_id) or chat_id != int(ADMIN_CHAT_ID):
                await answer_callback(callback["id"], "غير مسموح.")
                return {"ok": True}
            _, action, offer_id = data.split(":", 2)
            body = PENDING_OFFERS.get(offer_id)
            if not body:
                await answer_callback(callback["id"], "انتهت صلاحية هذا الطلب أو عولج مسبقاً.")
                return {"ok": True}
            if action == "publish":
                try:
                    await send_channel_message("📢 عرض جديد — ZERO BOT\n\n" + body)
                except Exception:
                    await answer_callback(callback["id"], "تعذر النشر؛ تحقق من صلاحيات البوت.")
                    return {"ok": True}
                PENDING_OFFERS.pop(offer_id, None)
                await answer_callback(callback["id"], "تم النشر.")
                await send_message(chat_id, "✅ تم نشر العرض في القناة.")
            elif action == "reject":
                PENDING_OFFERS.pop(offer_id, None)
                await answer_callback(callback["id"], "تم رفض العرض.")
                await send_message(chat_id, "❌ تم رفض العرض ولن يُنشر.")
            return {"ok": True}

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
