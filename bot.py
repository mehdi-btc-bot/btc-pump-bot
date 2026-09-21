import requests
import os
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

THRESHOLD_2MIN = 0.4
VOLUME_MULTIPLIER = 1.5
ALTCOINS = ["ETHUSDT", "SOLUSDT", "BNBUSDT"]
ALT_THRESHOLD = 0.3

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Sent: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")

def get_klines(symbol, interval, limit=3):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        return requests.get(url, timeout=10).json()
    except:
        return None

def get_change(symbol, interval, candles_back):
    klines = get_klines(symbol, interval, candles_back + 1)
    if not klines:
        return 0, 0
    old = float(klines[0][4])
    new = float(klines[-1][4])
    change = ((new - old) / old) * 100
    return change, new

def get_avg_volume():
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=20"
        data = requests.get(url, timeout=10).json()
        volumes = [float(c[7]) for c in data]
        return sum(volumes) / len(volumes)
    except:
        return 0

def get_current_volume():
    try:
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=1"
        data = requests.get(url, timeout=10).json()
        return float(data[0][7])
    except:
        return 0

def get_alt_changes(interval="2m"):
    results = {}
    for sym in ALTCOINS:
        change, _ = get_change(sym, interval, 2)
        results[sym] = change
    return results

def trend_label(value):
    if value > 0.1: return "🟢 صعودی"
    if value < -0.1: return "🔴 نزولی"
    return "⚪️ خنثی"

c2m, price = get_change("BTCUSDT", "1m", 2)
c15m, _ = get_change("BTCUSDT", "15m", 1)
c1h, _ = get_change("BTCUSDT", "1h", 1)

print(f"[{datetime.now().strftime('%H:%M:%S')}] BTC: ${price:,.2f} | 2m: {c2m:+.2f}% | 15m: {c15m:+.2f}% | 1h: {c1h:+.2f}%")

if abs(c2m) >= THRESHOLD_2MIN:
    direction = 1 if c2m > 0 else -1
    alignment_15m = (c15m * direction) >= 0.1
    alignment_1h = (c1h * direction) >= 0.1

    avg_vol = get_avg_volume()
    cur_vol = get_current_volume()
    vol_ratio = (cur_vol / avg_vol) if avg_vol else 0
    volume_ok = vol_ratio >= VOLUME_MULTIPLIER

    alts = get_alt_changes("2m")
    alt_confirms = sum(1 for ch in alts.values() if (ch * direction) >= ALT_THRESHOLD)
    alt_ok = alt_confirms >= 1

    score = 0
    if alignment_15m: score += 1
    if alignment_1h: score += 1
    if volume_ok: score += 1
    if alt_ok: score += 1

    emoji = "🚀" if c2m > 0 else "📉"
    if score == 4:
        status = "🔥 <b>سیگنال قوی</b> — همه تأیید کردن"
    elif score == 3:
        status = "✅ <b>سیگنال خوب</b> — تأیید نسبی"
    elif score == 2:
        status = "⚠️ <b>سیگنال ضعیف</b> — محتاط باش"
    else:
        status = "❌ <b>سیگنال مشکوک</b> — احتمالاً فیک"

    msg = (
        f"<b>{emoji} حرکت ۲ دقیقه‌ای بیت‌کوین</b>\n\n"
        f"{status}\n\n"
        f"📊 تغییر ۲ دقیقه: <b>{c2m:+.2f}%</b>\n"
        f"📊 روند ۱۵ دقیقه: {trend_label(c15m)} ({c15m:+.2f}%)\n"
        f"📊 روند ۱ ساعته: {trend_label(c1h)} ({c1h:+.2f}%)\n"
        f"💰 قیمت: <b>${price:,.2f}</b>\n"
        f"📈 حجم: {vol_ratio:.2f}x میانگین\n"
        f"🔗 آلت‌کوین‌ها:\n"
    )
    for sym, ch in alts.items():
        msg += f"   • {sym.replace('USDT','')}: {ch:+.2f}%\n"

    send_telegram_message(msg)
else:
    print("No significant move.")
