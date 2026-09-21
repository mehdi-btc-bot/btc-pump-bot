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
        print(f"Telegram sent: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_klines(symbol, interval, limit=3):
    try:
        bar_map = {"1m": "1m", "15m": "15m", "1H": "1H", "1h": "1H", "2m": "2m"}
        bar = bar_map.get(interval, interval)
        inst = symbol.replace('USDT', '-USDT')
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={bar}&limit={limit}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("code") != "0":
            print(f"OKX error: {data}")
            return None
        return list(reversed(data["data"]))
    except Exception as e:
        print(f"get_klines error: {e}")
        return None

def get_change(symbol, interval, candles_back):
    klines = get_klines(symbol, interval, candles_back + 1)
    if not klines or len(klines) < candles_back + 1:
        return 0, 0
    try:
        old = float(klines[0][4])
        new = float(klines[-1][4])
        change = ((new - old) / old) * 100
        return change, new
    except Exception as e:
        print(f"get_change parse error: {e}")
        return 0, 0

def get_avg_volume():
    try:
        klines = get_klines("BTCUSDT", "1m", 20)
        if not klines:
            return 0
        volumes = [float(c[5]) for c in klines]
        return sum(volumes) / len(volumes)
    except:
        return 0

def get_current_volume():
    try:
        klines = get_klines("BTCUSDT", "1m", 1)
        if not klines:
            return 0
        return float(klines[-1][5])
    except:
        return 0

def get_alt_changes(interval="1m"):
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
c1h, _ = get_change("BTCUSDT", "1H", 1)

print(f"[{datetime.now().strftime('%H:%M:%S')}] BTC: ${price:,.2f} | 2m: {c2m:+.2f}% | 15m: {c15m:+.2f}% | 1h: {c1h:+.2f}%")

if abs(c2m) >= THRESHOLD_2MIN:
    direction = 1 if c2m > 0 else -1
    alignment_15m = (c15m * direction) >= 0.1
    alignment_1h = (c1h * direction) >= 0.1

    avg_vol = get_avg_volume()
    cur_vol = get_current_volume()
    vol_ratio = (cur_vol / avg_vol) if avg_vol else 0
    volume_ok = vol_ratio >= VOLUME_MULTIPLIER

    alts = get_alt_changes("1m")
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
