import requests
import os
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ===== تنظیمات =====
VOLUME_SPIKE_5M = 2.0
VOLUME_SPIKE_15M = 1.8
VOLUME_SPIKE_1H = 1.5

MIN_PRICE_MOVE = 0.15

ALTCOINS = ["ETHUSDT", "SOLUSDT", "BNBUSDT"]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Telegram sent: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_klines(symbol, interval, limit=25):
    try:
        bar_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1H": "1H"}
        bar = bar_map.get(interval, interval)
        inst = symbol.replace('USDT', '-USDT')
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={bar}&limit={limit}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("code") != "0":
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
        return ((new - old) / old) * 100, new
    except:
        return 0, 0

def get_volume_ratio(symbol, interval, num_candles, avg_period=20):
    klines = get_klines(symbol, interval, avg_period + num_candles)
    if not klines or len(klines) < avg_period + num_candles:
        return 0
    try:
        volumes = [float(k[5]) for k in klines]
        recent = sum(volumes[-num_candles:]) / num_candles
        avg = sum(volumes[:-num_candles]) / (len(volumes) - num_candles)
        return recent / avg if avg > 0 else 0
    except:
        return 0

def calculate_rsi(symbol, interval="15m", period=14):
    klines = get_klines(symbol, interval, period + 2)
    if not klines or len(klines) < period + 1:
        return None
    try:
        closes = [float(k[4]) for k in klines[:-1]]
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            if diff > 0:
                gains.append(diff); losses.append(0)
            else:
                gains.append(0); losses.append(abs(diff))
        if len(gains) < period:
            return None
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)
    except:
        return None

def rsi_text(rsi):
    if rsi is None:
        return "📊 RSI: نامشخص"
    if rsi >= 70:
        return f"📊 RSI: <b>{rsi}</b> ⚠️ اشباع خرید"
    elif rsi <= 30:
        return f"📊 RSI: <b>{rsi}</b> 🔄 اشباع فروش"
    return f"📊 RSI: <b>{rsi}</b> (نرمال)"

def trend_label(v):
    if v > 0.05: return "🟢"
    if v < -0.05: return "🔴"
    return "⚪️"

# ===== محاسبات =====
_, price = get_change("BTCUSDT", "5m", 1)
c5m, _ = get_change("BTCUSDT", "5m", 1)
c15m, _ = get_change("BTCUSDT", "15m", 1)
c1h, _ = get_change("BTCUSDT", "1H", 1)

vol_5m = get_volume_ratio("BTCUSDT", "5m", 1, 20)
vol_15m = get_volume_ratio("BTCUSDT", "15m", 1, 20)
vol_1h = get_volume_ratio("BTCUSDT", "1H", 1, 20)

print(f"[{datetime.now().strftime('%H:%M:%S')}] BTC: ${price:,.2f}")
print(f"  Price 5m: {c5m:+.2f}% | 15m: {c15m:+.2f}% | 1h: {c1h:+.2f}%")
print(f"  Volume 5m: {vol_5m:.2f}x | 15m: {vol_15m:.2f}x | 1h: {vol_1h:.2f}x")

volume_alerts = []
if vol_5m >= VOLUME_SPIKE_5M:
    volume_alerts.append(("5 دقیقه", vol_5m))
if vol_15m >= VOLUME_SPIKE_15M:
    volume_alerts.append(("15 دقیقه", vol_15m))
if vol_1h >= VOLUME_SPIKE_1H:
    volume_alerts.append(("1 ساعته", vol_1h))

if volume_alerts:
    if c5m > MIN_PRICE_MOVE:
        direction_emoji = "🟢"
        direction_text = "<b>خریدارها فعال شدن</b> — فشار خرید"
    elif c5m < -MIN_PRICE_MOVE:
        direction_emoji = "🔴"
        direction_text = "<b>فروشنده‌ها فعال شدن</b> — فشار فروش"
    else:
        direction_emoji = "⚪️"
        direction_text = "<b>هنوز جهتی مشخص نیست</b> — منتظر باش"

    alt_lines = ""
    for sym in ALTCOINS:
        ch, _ = get_change(sym, "5m", 1)
        alt_lines += f"   • {sym.replace('USDT','')}: {ch:+.2f}%\n"

    rsi = calculate_rsi("BTCUSDT", "15m", 14)

    msg = f"{direction_emoji} <b>بیدار شدن بازار بیت‌کوین</b>\n\n"
    msg += f"{direction_text}\n\n"

    msg += "📊 <b>جهش حجم:</b>\n"
    for tf, ratio in volume_alerts:
        msg += f"   • {tf}: <b>{ratio:.2f}x</b> میانگین\n"

    msg += f"\n💰 قیمت: <b>${price:,.2f}</b>\n"
    msg += f"\n📈 <b>حرکت قیمت:</b>\n"
    msg += f"   • 5 دقیقه: {trend_label(c5m)} {c5m:+.2f}%\n"
    msg += f"   • 15 دقیقه: {trend_label(c15m)} {c15m:+.2f}%\n"
    msg += f"   • 1 ساعته: {trend_label(c1h)} {c1h:+.2f}%\n"

    msg += f"\n🔗 <b>آلت‌کوین‌ها:</b>\n{alt_lines}"
    msg += f"\n{rsi_text(rsi)}\n\n"
    msg += "💡 <i>برو پای چارت و تحلیل کن.</i>"

    send_telegram_message(msg)
else:
    print("بازار آرومه — حجمی وارد نشده.")
