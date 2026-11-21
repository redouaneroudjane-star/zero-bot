
import os
import re
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

SOURCES = {
    "Djezzy": "https://www.djezzy.dz/",
    "Ooredoo": "https://www.ooredoo.dz/",
    "Mobilis": "https://mobilis.dz/",
}

KEYWORDS = [
    "offre", "promotion", "promo", "gratuit",
    "internet", "bonus", "forfait", "عرض",
    "مجاني", "تخفيض", "انترنت"
]

async def send_message(client, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = await client.post(
        url,
        data={"chat_id": ADMIN_CHAT_ID, "text": text,
              "disable_web_page_preview": True}
    )
    response.raise_for_status()

async def scan_source(client, network, url):
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        page = response.text.lower()

        found = [word for word in KEYWORDS if word.lower() in page]

        if found:
            message = (
                f"🔎 فحص موقع {network}\n"
                f"عُثر على كلمات مرتبطة بالعروض.\n\n"
                f"الكلمات: {', '.join(found)}\n"
                f"المصدر الرسمي: {url}\n\n"
                "⚠️ هذه نتيجة أولية وليست عرضًا مؤكدًا. "
                "تحقق من الصفحة يدويًا قبل النشر."
            )
            await send_message(client, message)

        print(f"{network}: scan completed")

    except Exception as error:
        print(f"{network}: {error}")

async def main():
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        raise RuntimeError("Missing BOT_TOKEN or ADMIN_CHAT_ID")

    async with httpx.AsyncClient(timeout=30) as client:
        for network, url in SOURCES.items():
            await scan_source(client, network, url)

if __name__ == "__main__":
    asyncio.run(main())
