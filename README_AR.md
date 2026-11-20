# ZERO BOT — نسخة تجريبية

## الملفات
- `main.py`: كود البوت وقائمة Telegram التفاعلية.
- `requirements.txt`: مكتبات Python.
- `render.yaml`: إعداد خدمة Render.

## النشر على Render
1. ارفع الملفات الثلاثة إلى مستودع GitHub جديد.
2. في Render اختر New > Web Service ثم اربط المستودع.
3. استخدم إعدادات `render.yaml` أو أدخل:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. أضف متغير البيئة `BOT_TOKEN` وضع Token الجديد في Render فقط.
5. أضف `WEBHOOK_SECRET` بقيمة طويلة عشوائية، مثلاً 32 حرفاً أو أكثر.
6. بعد النشر، افتح رابط الخدمة؛ يجب أن ترى `ZERO BOT is running`.
7. افتح البوت في Telegram وأرسل `/start`.

## ملاحظات مهمة
- لا تضع Token في GitHub ولا ترسله في المحادثات.
- هذه نسخة أولية تعرض مصادر رسمية وإرشادات فقط؛ لا تدّعي أن عرضاً مجانياً متاح لكل رقم.
- لا تجمع كلمات المرور أو رموز SMS.
- خطة Render المجانية قد تتوقف عند الخمول؛ قد يتأخر أول رد بعد الاستيقاظ.
- لا يوجد تفعيل آلي للعروض إلا إذا وفر المتعامل طريقة رسمية تسمح به.
