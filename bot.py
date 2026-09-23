import requests
import os
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

WATCHLIST = [
    "BTCUSDT", "SOLUSDT", "BCHUSDT", "SUIUSDT", "LTCUSDT", "UNIUSDT", "XRPUSDT",
    "TRXUSDT", "DOGEUSDT", "DOTUSDT", "XLMUSDT", "BNBUSDT", "AVAXUSDT", "LINKUSDT",
    "LDOUSDT", "XAUTUSDT", "OPUSDT", "ADAUSDT", "HYPEUSDT", "ETCUSDT", "APTUSDT",
    "ETHUSDT", "FARTCOINUSDT", "TAOUSDT", "ZECUSDT", "INJUSDT", "DYDXUSDT", "CRVUSDT"
]

# تایم‌فریم اصلی سیگنال (سریع)
SIGNAL_TF = "5m"
# تایم‌فریم تأیید (فیلتر نویز)
CONFIRM_TF = "15m"

VOLUME_MA_PERIOD = 20
RSI_PERIOD = 14
RSI_MA_PERIOD = 14
VOLUME_MULT = 1.3
MIN_SCORE = 4.5

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("Telegram sent")
    except Exception as e:
        print(f"TG error: {e}")

def get_klines(symbol, interval, limit=100):
    try:
        inst = symbol.replace('USDT', '-USDT')
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={interval}&limit={limit}"
        r = requests.get(url, timeout=10).json()
        if r.get("code") != "0":
            return None
        return list(reversed(r["data"]))
    except:
        return None

def calculate_ma(values, period):
    if len(values) < period:
        return None
    return [sum(values[i-period+1:i+1]) / period for i in range(period-1, len(values))]

def calculate_ema(values, period):
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = [sum(values[:period]) / period]
    for i in range(period, len(values)):
        ema.append((values[i] - ema[-1]) * multiplier + ema[-1])
    return ema

def calculate_rsi_series(closes, period=14):
    if len(closes) < period + 1:
        return None
    rsi_values = []
    for i in range(period, len(closes)):
        gains, losses = 0, 0
        for j in range(i - period + 1, i + 1):
            diff = closes[j] - closes[j-1]
            if diff > 0:
                gains += diff
            else:
                losses += abs(diff)
        avg_gain = gains / period
        avg_loss = losses / period
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))
    return rsi_values

def get_rsi_now(symbol, interval="1H"):
    klines = get_klines(symbol, interval, 60)
    if not klines or len(klines) < 20:
        return None
    closes = [float(k[4]) for k in klines]
    rsi_series = calculate_rsi_series(closes, RSI_PERIOD)
    if not rsi_series:
        return None
    return rsi_series[-1]

def get_change(symbol, interval, candles_back):
    klines = get_klines(symbol, interval, candles_back + 1)
    if not klines or len(klines) < candles_back + 1:
        return 0
    try:
        old = float(klines[0][4])
        new = float(klines[-1][4])
        return ((new - old) / old) * 100
    except:
        return 0

def get_trend(symbol, interval):
    klines = get_klines(symbol, interval, 100)
    if not klines or len(klines) < 55:
        return 0
    closes = [float(k[4]) for k in klines]
    ema20 = calculate_ema(closes, 20)
    ema50 = calculate_ema(closes, 50)
    if not ema20 or not ema50:
        return 0
    diff_pct = (ema20[-1] - ema50[-1]) / ema50[-1] * 100
    if diff_pct > 0.2:
        return 1
    elif diff_pct < -0.2:
        return -1
    return 0

def check_signal_on_tf(symbol, tf):
    """چک سیگنال روی یه تایم‌فریم خاص"""
    klines = get_klines(symbol, tf, 100)
    if not klines or len(klines) < 50:
        return None

    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]

    vol_ma_series = calculate_ma(volumes, VOLUME_MA_PERIOD)
    if not vol_ma_series:
        return None

    rsi_series = calculate_rsi_series(closes, RSI_PERIOD)
    if not rsi_series or len(rsi_series) < RSI_MA_PERIOD + 2:
        return None
    rsi_ma_series = calculate_ma(rsi_series, RSI_MA_PERIOD)
    if not rsi_ma_series:
        return None

    # آخرین کندل بسته شده
    i = 2
    vol_idx = len(volumes) - i
    ma_idx = vol_idx - (VOLUME_MA_PERIOD - 1)
    if ma_idx < 0:
        return None

    vol_now = volumes[vol_idx]
    vol_ma_now = vol_ma_series[ma_idx]
    vol_ratio = vol_now / vol_ma_now if vol_ma_now > 0 else 0

    rsi_idx = vol_idx - RSI_PERIOD
    rsi_ma_idx = rsi_idx - (RSI_MA_PERIOD - 1)
    if rsi_idx < 1 or rsi_ma_idx < 1:
        return None

    rsi_curr = rsi_series[rsi_idx]
    rsi_prev = rsi_series[rsi_idx - 1]
    ma_curr = rsi_ma_series[rsi_ma_idx]
    ma_prev = rsi_ma_series[rsi_ma_idx - 1]

    cross_up = rsi_prev < ma_prev and rsi_curr > ma_curr
    cross_down = rsi_prev > ma_prev and rsi_curr < ma_curr

    if vol_ratio < VOLUME_MULT:
        return None
    if not (cross_up or cross_down):
        return None

    return {
        "direction": 1 if cross_up else -1,
        "vol_ratio": vol_ratio,
        "rsi": rsi_curr,
        "rsi_ma": ma_curr,
        "price": closes[vol_idx]
    }

def check_symbol(symbol):
    # 1. سیگنال روی 5 دقیقه (سریع)
    sig_5m = check_signal_on_tf(symbol, SIGNAL_TF)
    if not sig_5m:
        return None

    direction = sig_5m["direction"]

    # 2. تأیید روی 15 دقیقه (فیلتر نویز)
    confirm_15m = check_signal_on_tf(symbol, CONFIRM_TF)
    confirm_15m_match = False
    if confirm_15m and confirm_15m["direction"] == direction:
        confirm_15m_match = True

    # 3. RSI 1h هم‌جهت
    rsi_1h = get_rsi_now(symbol, "1H")
    if rsi_1h is None:
        return None

    if direction == 1 and rsi_1h < 50:
        return None
    if direction == -1 and rsi_1h > 50:
        return None

    # 4. بلاک اشباع
    if direction == 1 and sig_5m["rsi"] > 75:
        return None
    if direction == -1 and sig_5m["rsi"] < 25:
        return None

    # ===== امتیازدهی =====
    score = 0
    details = []

    # 1. حجم
    if sig_5m["vol_ratio"] >= 2.0:
        score += 2
        details.append(f"✅ حجم قوی (5m): <b>{sig_5m['vol_ratio']:.2f}x</b>")
    elif sig_5m["vol_ratio"] >= 1.5:
        score += 1.5
        details.append(f"✅ حجم خوب (5m): <b>{sig_5m['vol_ratio']:.2f}x</b>")
    else:
        score += 1
        details.append(f"✅ حجم کافی (5m): <b>{sig_5m['vol_ratio']:.2f}x</b>")

    # 2. تأیید 15 دقیقه (وزن بالا چون مهمه)
    if confirm_15m_match:
        score += 2
        details.append(f"✅ تأیید 15m هم‌جهت (Vol: {confirm_15m['vol_ratio']:.2f}x)")
    else:
        details.append(f"⚠️ 15m تأیید نکرد")

    # 3. RSI 1h
    if direction == 1:
        if rsi_1h >= 60:
            score += 1.5
            details.append(f"✅ RSI 1h قوی: <b>{rsi_1h:.1f}</b>")
        else:
            score += 1
            details.append(f"✅ RSI 1h بالای 50: <b>{rsi_1h:.1f}</b>")
    else:
        if rsi_1h <= 40:
            score += 1.5
            details.append(f"✅ RSI 1h ضعیف: <b>{rsi_1h:.1f}</b>")
        else:
            score += 1
            details.append(f"✅ RSI 1h زیر 50: <b>{rsi_1h:.1f}</b>")

    # 4. روند 4 ساعته
    trend_4h = get_trend(symbol, "4H")
    if trend_4h == direction:
        score += 1
        details.append(f"✅ روند 4h هم‌جهت")
    elif trend_4h == 0:
        details.append(f"⚪️ روند 4h خنثی")
    else:
        score -= 0.5
        details.append(f"❌ روند 4h مخالف")

    # 5. RSI 5m ناحیه
    if 40 <= sig_5m["rsi"] <= 60:
        score += 1
        details.append(f"✅ RSI 5m ایده‌آل: <b>{sig_5m['rsi']:.1f}</b>")
    elif 30 <= sig_5m["rsi"] <= 70:
        score += 0.5
        details.append(f"✅ RSI 5m نرمال: <b>{sig_5m['rsi']:.1f}</b>")

    if score >= MIN_SCORE:
        return {
            "symbol": symbol,
            "price": sig_5m["price"],
            "vol_ratio": sig_5m["vol_ratio"],
            "rsi": sig_5m["rsi"],
            "rsi_ma": sig_5m["rsi_ma"],
            "rsi_1h": rsi_1h,
            "direction": "up" if direction == 1 else "down",
            "score": round(score, 1),
            "details": details,
            "confirm_15m": confirm_15m_match
        }
    return None

print(f"[{datetime.now().strftime('%H:%M:%S')}] بررسی {len(WATCHLIST)} ارز...")

signals = []
for symbol in WATCHLIST:
    try:
        r = check_symbol(symbol)
        if r:
            signals.append(r)
            print(f"  >> {symbol}: امتیاز {r['score']} | 15m تأیید: {r['confirm_15m']}")
    except Exception as e:
        print(f"  {symbol}: {e}")

print(f"تعداد سیگنال: {len(signals)}")

for sig in signals:
    symbol = sig["symbol"].replace("USDT", "")
    if sig["direction"] == "up":
        emoji = "🟢"
        title = "سیگنال صعودی"
    else:
        emoji = "🔴"
        title = "سیگنال نزولی"

    if sig["score"] >= 7:
        grade = "🔥 طلایی"
    elif sig["score"] >= 6:
        grade = "✅ قوی"
    else:
        grade = "⚠️ قابل قبول"

    ch5m = get_change(sig["symbol"], "5m", 1)
    ch1h = get_change(sig["symbol"], "1H", 1)

    # اگه 15m تأیید کرده، علامت خاص
    confirm_badge = "🔥 تأیید 15m" if sig["confirm_15m"] else "⚠️ بدون تأیید 15m"

    msg = f"{emoji} <b>{title} — {symbol}</b>\n"
    msg += f"{grade} | امتیاز: <b>{sig['score']}/7.5</b>\n"
    msg += f"{confirm_badge}\n"
    msg += f"⏱ {datetime.now().strftime('%H:%M:%S')}\n\n"
    msg += f"💰 قیمت: <b>${sig['price']:,.4f}</b>\n\n"
    msg += "<b>📋 تأییدها:</b>\n"
    for d in sig["details"]:
        msg += f"{d}\n"
    msg += f"\n📊 RSI 5m: <b>{sig['rsi']:.1f}</b> | MA: {sig['rsi_ma']:.1f}\n"
    msg += f"📊 RSI 1h: <b>{sig['rsi_1h']:.1f}</b>\n"
    msg += f"📈 قیمت 5m: {ch5m:+.2f}% | 1h: {ch1h:+.2f}%\n"
    msg += "\n💡 <i>برو پای چارت.</i>"

    send_telegram_message(msg)
