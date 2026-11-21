import os
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

SOURCES = {
    "Djezzy": "https://www.djezzy.dz/",
    "Ooredoo": "https://www.ooredoo.dz/",
    "Mobilis": "https://mobilis.dz/"
}

KEYWORDS = [
    "offre", "promotion", "promo",
    "internet", "gratuit", "bonus",
    "عرض", "مجاني", "انترنت"
]


async def main():
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        print("Missing scanner environment variables")
        return

    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True
    ) as client:

        for network, url in SOURCES.items():
            try:
                response = await client.get(url)
                response.raise_for_status()

                content = response.text.lower()
                found = [word for word in KEYWORDS if word in content]

                if found:
                    message = (
                        f"🔎 فحص موقع {network}\n"
                        "ظهرت كلمات قد تشير إلى عروض.\n"
                        "هذا تنبيه أولي فقط، وليس تأكيداً لوجود عرض جديد.\n"
                        f"الموقع: {url}\n"
                        f"الكلمات: {', '.join(found)}"
                    )

                    await client.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": ADMIN_CHAT_ID,
                            "text": message
                        }
                    )

                print(f"Scanned {network}")

            except Exception as error:
                print(f"{network}: {error}")


if __name__ == "__main__":
    asyncio.run(main())
