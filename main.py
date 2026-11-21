import os
import re
import html
import logging
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request, HTTPException

from database import (
    init_db,
    save_user,
    set_user_network,
    set_user_notifications,
    create_offer,
    get_offer,
    set_offer_status,
    list_pending_offers,
    list_approved_offers,
    list_subscribers,
    get_stats,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("zero-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
PUBLIC_URL = os.getenv("RENDER_EXTERNAL_URL")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

ADMINS = {
    x.strip() for x in ADMIN_CHAT_ID.split(",") if x.strip()
}

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI(title="ZERO-BOT")


NETWORKS = {
    "djezzy": {
        "name": "Djezzy",
        "domain": "djezzy.dz"
    },
    "ooredoo": {
        "name": "Ooredoo",
        "domain": "ooredoo.dz"
    },
    "mobilis": {
        "name": "Mobilis",
        "domain": "mobilis.dz"
    }
}


def is_admin(user_id):
    return str(user_id) in ADMINS


async def telegram(method, payload=None):
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            f"{API}/{method}",
            json=payload or {}
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            raise RuntimeError(str(data))

        return data.get("result")


async def send_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    return await telegram("sendMessage", payload)


async def answer_callback(callback_id, text=""):
    try:
        await telegram("answerCallbackQuery", {
            "callback_query_id": callback_id,
            "text": text
        })
    except Exception:
        log.exception("Callback answer failed")


def main_keyboard():
    return {
        "keyboard": [
            [{"text": "📡 العروض"}, {"text": "📱 شبكتي"}],
            [{"text": "🔔 الإشعارات"}, {"text": "📨 إرسال عرض"}],
            [{"text": "📊 آخر العروض"}, {"text": "ℹ️ المساعدة"}]
        ],
        "resize_keyboard": True
    }


def network_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "Djezzy", "callback_data": "net_djezzy"},
                {"text": "Ooredoo", "callback_data": "net_ooredoo"}
            ],
            [
                {"text": "Mobilis", "callback_data": "net_mobilis"},
                {"text": "كل الشبكات", "callback_data": "net_all"}
            ]
        ]
    }


def notification_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "تفعيل 🔔", "callback_data": "notify_on"},
                {"text": "إيقاف 🔕", "callback_data": "notify_off"}
            ]
        ]
    }


def admin_keyboard(offer_id):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ قبول ونشر",
                    "callback_data": f"approve_{offer_id}"
                },
                {
                    "text": "❌ رفض",
                    "callback_data": f"reject_{offer_id}"
                }
            ]
        ]
    }


def valid_official_source(network, url):
    if network not in NETWORKS:
        return False

    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        official = NETWORKS[network]["domain"]

        return (
            parsed.scheme == "https"
            and (host == official or host.endswith("." + official))
        )
    except Exception:
        return False


def parse_candidate(text):
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) < 6:
        return None

    if lines[0].lower() != "/candidate":
        return None

    title = lines[1]
    network_text = lines[1].lower()

    if "djezzy" in network_text:
        network = "djezzy"
    elif "ooredoo" in network_text:
        network = "ooredoo"
    elif "mobilis" in network_text:
        network = "mobilis"
    else:
        return None

    details = lines[2]
    conditions = lines[3]
    source_url = lines[4].replace("المصدر الرسمي:", "").strip()
    expiry = lines[5].replace("تاريخ الانتهاء:", "").strip()

    if not valid_official_source(network, source_url):
        return None

    return {
        "title": title,
        "network": network,
        "details": details,
        "conditions": conditions,
        "source_url": source_url,
        "expiry": expiry
    }


async def publish_offer(offer):
    network_name = NETWORKS[offer["network"]]["name"]

    message = (
        f"🎁 <b>{html.escape(offer['title'])}</b>\n\n"
        f"📡 الشبكة: {network_name}\n"
        f"📋 التفاصيل: {html.escape(offer['details'])}\n"
        f"📝 الشروط: {html.escape(offer['conditions'])}\n"
        f"⏳ الانتهاء: {html.escape(offer['expiry'])}\n\n"
        f"🔗 <a href=\"{html.escape(offer['source_url'], quote=True)}\">"
        f"المصدر الرسمي</a>\n\n"
        f"⚠️ تحقق من شروط العرض لدى المشغل قبل الاشتراك."
    )

    await send_message(CHANNEL_ID, message)


async def notify_subscribers(offer):
    users = list_subscribers(offer["network"])

    message = (
        f"🔔 <b>عرض جديد!</b>\n\n"
        f"{html.escape(offer['title'])}\n"
        f"{html.escape(offer['details'])}\n"
        f"🔗 {html.escape(offer['source_url'])}"
    )

    for user in users:
        try:
            await send_message(user["user_id"], message)
        except Exception:
            log.warning("Could not notify user %s", user["user_id"])


@app.on_event("startup")
async def startup():
    init_db()

    if BOT_TOKEN and PUBLIC_URL:
        try:
            await telegram("setWebhook", {
                "url": PUBLIC_URL.rstrip("/") + "/webhook",
                "secret_token": WEBHOOK_SECRET
            })
            log.info("Webhook configured")
        except Exception:
            log.exception("Webhook configuration failed")


@app.get("/")
async def health():
    return {"status": "online", "bot": "ZERO-BOT"}


@app.post("/webhook")
async def webhook(request: Request):
    if WEBHOOK_SECRET:
        supplied = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if supplied != WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Forbidden")

    update = await request.json()

    if "callback_query" in update:
        await handle_callback(update["callback_query"])
        return {"ok": True}

    message = update.get("message")

    if message:
        await handle_message(message)

    return {"ok": True}


async def handle_message(message):
    chat = message.get("chat", {})
    user = message.get("from", {})
    user_id = user.get("id")

    if not user_id:
        return

    chat_id = chat.get("id")

    save_user(
        user_id,
        user.get("username"),
        user.get("first_name")
    )

    text = message.get("text", "").strip()

    if not text:
        return

    if text.startswith("/start"):
        await send_message(
            chat_id,
            "👋 أهلاً بك في <b>ZERO-BOT</b>\n\n"
            "بوت متابعة عروض الاتصالات الجزائرية.\n"
            "اختر الخدمة من القائمة.",
            main_keyboard()
        )
        return

    if text.startswith("/help") or text == "ℹ️ المساعدة":
        await send_message(
            chat_id,
            "📌 <b>مساعدة ZERO-BOT</b>\n\n"
            "/start - القائمة الرئيسية\n"
            "/myid - معرفة رقم حسابك\n"
            "/candidate - إرسال عرض للمراجعة\n"
            "/offers - آخر العروض\n"
            "/admin - لوحة المشرف\n\n"
            "لا ترسل كلمات المرور أو رموز التحقق."
        )
        return

    if text.startswith("/myid"):
        await send_message(chat_id, f"رقم حسابك: <code>{user_id}</code>")
        return

    if text.startswith("/candidate"):
        await send_message(
            chat_id,
            "أرسل العرض بهذا الشكل:\n\n"
            "<code>/candidate\n"
            "اسم العرض والشبكة\n"
            "التفاصيل والسعر/الحجم والمدة\n"
            "الشروط والأهلية\n"
            "المصدر الرسمي: https://...\n"
            "تاريخ الانتهاء أو غير محدد</code>\n\n"
            "يجب أن يكون الرابط من الموقع الرسمي للشبكة."
        )
        return

    if text.startswith("/offers") or text == "📊 آخر العروض":
        offers = list_approved_offers(10)

        if not offers:
            await send_message(chat_id, "لا توجد عروض منشورة حالياً.")
            return

        for offer in offers:
            await send_message(
                chat_id,
                f"🎁 <b>{html.escape(offer['title'])}</b>\n"
                f"{html.escape(offer['details'])}\n"
                f"🔗 {html.escape(offer['source_url'])}"
            )
        return

    if text == "📡 العروض":
        await send_message(
            chat_id,
            "اختر شبكتك لتلقي العروض المناسبة.",
            network_keyboard()
        )
        return

    if text == "📱 شبكتي":
        await send_message(
            chat_id,
            "اختر الشبكة التي تستخدمها:",
            network_keyboard()
        )
        return

    if text == "🔔 الإشعارات":
        await send_message(
            chat_id,
            "إدارة إشعارات العروض:",
            notification_keyboard()
        )
        return

    if text == "📨 إرسال عرض":
        await send_message(
            chat_id,
            "لإرسال عرض للمراجعة استخدم الأمر /candidate"
        )
        return

    if text.startswith("/admin"):
        if not is_admin(user_id):
            await send_message(chat_id, "ليس لديك صلاحية المشرف.")
            return

        stats = get_stats()

        await send_message(
            chat_id,
            "🛠 <b>لوحة المشرف</b>\n\n"
            f"👥 المستخدمون: {stats['users']}\n"
            f"⏳ قيد المراجعة: {stats['pending']}\n"
            f"✅ المنشورة: {stats['approved']}\n"
            f"❌ المرفوضة: {stats['rejected']}\n\n"
            "استخدم /pending لمراجعة العروض."
        )
        return

    if text.startswith("/pending"):
        if not is_admin(user_id):
            return

        offers = list_pending_offers()

        if not offers:
            await send_message(chat_id, "لا توجد عروض معلقة.")
            return

        for offer in offers:
            await send_message(
                chat_id,
                f"📝 <b>عرض للمراجعة #{offer['id']}</b>\n"
                f"{html.escape(offer['title'])}\n"
                f"{html.escape(offer['details'])}\n"
                f"{html.escape(offer['source_url'])}",
                admin_keyboard(offer["id"])
            )
        return

    if text.startswith("/candidate"):
        return

    candidate = parse_candidate(text)

    if candidate:
        offer_id = create_offer(
            candidate["title"],
            candidate["network"],
            candidate["details"],
            candidate["conditions"],
            candidate["source_url"],
            candidate["expiry"],
            user_id
        )

        if not offer_id:
            await send_message(chat_id, "هذا العرض مسجل مسبقاً.")
            return

        await send_message(
            chat_id,
            f"✅ استلمنا العرض رقم #{offer_id}.\n"
            "سيتم مراجعته قبل نشره."
        )

        for admin in ADMINS:
            try:
                await send_message(
                    int(admin),
                    f"📥 <b>عرض جديد للمراجعة #{offer_id}</b>\n"
                    f"{html.escape(candidate['title'])}\n"
                    f"{html.escape(candidate['details'])}\n"
                    f"🔗 {html.escape(candidate['source_url'])}",
                    admin_keyboard(offer_id)
                )
            except Exception:
                log.exception("Admin notification failed")

        return

    await send_message(
        chat_id,
        "لم أفهم طلبك. استخدم القائمة أو /help."
    )


async def handle_callback(callback):
    data = callback.get("data", "")
    user_id = callback.get("from", {}).get("id")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    callback_id = callback.get("id")

    if not user_id:
        return

    if data.startswith("net_"):
        network = data.replace("net_", "")

        if network not in ("djezzy", "ooredoo", "mobilis", "all"):
            await answer_callback(callback_id, "اختيار غير صالح")
            return

        set_user_network(user_id, network)
        await answer_callback(callback_id, "تم حفظ شبكتك")
        await send_message(chat_id, "✅ تم حفظ اختيار الشبكة.")
        return

    if data == "notify_on":
        set_user_notifications(user_id, True)
        await answer_callback(callback_id, "تم تفعيل الإشعارات")
        return

    if data == "notify_off":
        set_user_notifications(user_id, False)
        await answer_callback(callback_id, "تم إيقاف الإشعارات")
        return

    if data.startswith("approve_") or data.startswith("reject_"):
        if not is_admin(user_id):
            await answer_callback(callback_id, "غير مصرح لك")
            return

        action, raw_id = data.split("_", 1)

        try:
            offer_id = int(raw_id)
        except ValueError:
            await answer_callback(callback_id, "رقم غير صالح")
            return

        offer = get_offer(offer_id)

        if not offer or offer["status"] != "pending":
            await answer_callback(callback_id, "العرض غير موجود أو تمت مراجعته")
            return

        if action == "approve":
            if not CHANNEL_ID:
                await answer_callback(callback_id, "CHANNEL_ID غير مضبوط")
                return

            try:
                await publish_offer(offer)
            except Exception:
                log.exception("Publishing failed")
                await answer_callback(callback_id, "فشل النشر، لم يتم اعتماد العرض")
                return

            set_offer_status(offer_id, "approved")

            await notify_subscribers(offer)

            await answer_callback(callback_id, "تم النشر")
            await send_message(chat_id, f"✅ تم نشر العرض #{offer_id}")

        else:
            set_offer_status(offer_id, "rejected")
            await answer_callback(callback_id, "تم رفض العرض")
            await send_message(chat_id, f"❌ تم رفض العرض #{offer_id}")
