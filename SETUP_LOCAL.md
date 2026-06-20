# راه‌اندازی لوکال MatchPulse روی ویندوز

این فایل برای راه‌اندازی سریع پروژه MatchPulse روی سیستم لوکال است.

## 1. گرفتن آخرین نسخه پروژه

در CMD وارد مسیر پروژه شو:

```cmd
cd C:\Users\mhadd\matchpulse
```

بعد آخرین نسخه را از GitHub بگیر:

```cmd
git pull origin main
```

اگر پروژه را روی سیستم جدید هنوز clone نکرده‌ای:

```cmd
git clone https://github.com/mreza0007/matchpulse.git
cd matchpulse
```

## 2. فایل env بک‌اند

مسیر فایل env بک‌اند:

```text
backend\.env
```

این فایل باید وجود داشته باشد و کلیدهای زیر را داشته باشد:

```env
BOT_TOKEN=
WEBAPP_URL=
FOOTBALL_API_TOKEN=
LIVE_SCORE_SYNC_ENABLED=true
```

نکته مهم: توکن واقعی را داخل GitHub push نکن.

## 3. فایل env فرانت‌اند

مسیر فایل env فرانت‌اند:

```text
backend\frontend\.env
```

مقدار لازم:

```env
VITE_API_URL=/api
```

## 4. اجرای بک‌اند

از ریشه پروژه این فایل را اجرا کن:

```cmd
start-backend.bat
```

یا دستی:

```cmd
cd C:\Users\mhadd\matchpulse\backend
venv\Scripts\activate
uvicorn main:api --port 8000
```

بک‌اند باید روی این آدرس بالا بیاید:

```text
http://127.0.0.1:8000
```

## 5. اجرای فرانت‌اند

از ریشه پروژه این فایل را اجرا کن:

```cmd
start-frontend.bat
```

یا دستی:

```cmd
cd C:\Users\mhadd\matchpulse\backend\frontend
npm run dev
```

فرانت‌اند باید روی این آدرس بالا بیاید:

```text
http://127.0.0.1:5173
```

## 6. اجرای ngrok برای تست تلگرام

در CMD جداگانه بزن:

```cmd
ngrok http 5173
```

ngrok یک آدرس شبیه این می‌دهد:

```text
https://example.ngrok-free.dev
```

اگر آدرس ngrok عوض شد، ممکن است لازم باشد این موارد را هم آپدیت کنی:

* مقدار `WEBAPP_URL` در `backend\.env`
* آدرس Web App در BotFather
* آدرس Mini App مربوط به ربات تلگرام

## 7. تست سلامت پروژه

بعد از اینکه backend و frontend روشن شدند، از ریشه پروژه اجرا کن:

```cmd
check-local.bat
```

این فایل این موارد را چک می‌کند:

* وضعیت Git
* اتصال مستقیم به backend
* اتصال frontend proxy به backend

اگر تست frontend proxy به جای JSON، فایل HTML برگرداند، یعنی `vite.config.js` مشکل proxy دارد.

## 8. ترتیب پیشنهادی اجرای پروژه

هر بار برای تست لوکال:

1. اجرای backend:

```cmd
start-backend.bat
```

2. اجرای frontend:

```cmd
start-frontend.bat
```

3. اجرای ngrok:

```cmd
ngrok http 5173
```

4. تست سلامت:

```cmd
check-local.bat
```

## 9. نکته‌های مهم

قبل از شروع کار روی هر سیستم:

```cmd
git pull origin main
```

بعد از تغییرات مهم:

```cmd
git status
git add .
git commit -m "your message"
git push origin main
```

هیچ‌وقت فایل‌های `.env` یا توکن‌ها را push نکن.
