import requests
import os
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# ===== لیست 28 ارز =====
WATCHLIST = [
    "BTCUSDT", "SOLUSDT", "BCHUSDT", "SUIUSDT", "LTCUSDT", "UNIUSDT", "XRPUSDT",
    "TRXUSDT", "DOGEUSDT", "DOTUSDT", "XLMUSDT", "BNBUSDT", "AVAXUSDT", "LINKUSDT",
    "LDOUSDT", "XAUTUSDT", "OPUSDT", "ADAUSDT", "HYPEUSDT", "ETCUSDT", "APTUSDT",
    "ETHUSDT", "FARTCOINUSDT", "TAOUSDT", "ZECUSDT", "INJUSDT", "DYDXUSDT", "CRVUSDT"
]

# ===== تنظیمات =====
TIMEFRAME = "15m"
VOLUME_MA_PERIOD = 20
RSI_PERIOD = 14
RSI_MA_PERIOD = 14
VOLUME_MULT = 1.2
LOOKBACK_CANDLES = 2  # چند کندل اخیر رو چک کن

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Telegram sent: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_klines(symbol, interval, limit=100):
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
        return None

def calculate_ma(values, period):
    if len(values) < period:
        return None
    return [sum(values[i-period+1:i+1]) / period for i in range(period-1, len(values))]

def calculate_rsi_series(closes, period=14):
    if len(closes) < period + 1:
        return None
    rsi_values = []
    for i in range(period, len(closes)):
        gains = 0
        losses = 0
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

def check_symbol(symbol):
    klines = get_klines(symbol, TIMEFRAME, 100)
    if not klines or len(klines) < 50:
        return None
    
    closes = [float(k[4]) for k in klines]
    volumes = [float(k[5]) for k in klines]
    current_price = closes[-1]
    
    # Volume MA
    vol_ma_series = calculate_ma(volumes, VOLUME_MA_PERIOD)
    if not vol_ma_series:
        return None
    
    # RSI + RSI MA
    rsi_series = calculate_rsi_series(closes, RSI_PERIOD)
    if not rsi_series or len(rsi_series) < RSI_MA_PERIOD + 2:
        return None
    rsi_ma_series = calculate_ma(rsi_series, RSI_MA_PERIOD)
    if not rsi_ma_series:
        return None
    
    # ===== محاسبه Volume Ratio برای هر کندل =====
    # vol_ma_series از ایندکس (VOLUME_MA_PERIOD-1) از volumes شروع می‌شه
    # پس برای هر کندل i در volumes، نسبتش = volumes[i] / vol_ma_series[i - (VOLUME_MA_PERIOD-1)]
    
    # ===== چک کردن همزمانی روی N کندل اخیر =====
    # برای هر کندل اخیر، چک می‌کنیم که:
    # 1. حجم همون کندل >= VOLUME_MULT * MA اون زمان
    # 2. RSI روی همون کندل کراس کرده
    
    for i in range(1, LOOKBACK_CANDLES + 1):
        # ایندکس کندل فعلی در volumes (از آخر به اول)
        vol_idx = len(volumes) - i
        # ایندکس متناظر در vol_ma_series
        ma_idx = vol_idx - (VOLUME_MA_PERIOD - 1)
        
        if ma_idx < 0 or vol_idx < 0:
            continue
        
        # محاسبه Volume Ratio برای همین کندل
        vol_now = volumes[vol_idx]
        vol_ma_now = vol_ma_series[ma_idx]
        vol_ratio_candle = vol_now / vol_ma_now if vol_ma_now > 0 else 0
        
        # ایندکس RSI برای همین کندل
        # rsi_series با ایندکس RSI_PERIOD در closes شروع می‌شه
        rsi_idx = vol_idx - RSI_PERIOD
        rsi_ma_idx = rsi_idx - (RSI_MA_PERIOD - 1)
        
        if rsi_idx < 1 or rsi_ma_idx < 1:
            continue
        
        # RSI روی همین کندل و کندل قبل
        rsi_curr = rsi_series[rsi_idx] if rsi_idx < len(rsi_series) else None
        rsi_prev = rsi_series[rsi_idx - 1] if rsi_idx - 1 >= 0 else None
        ma_curr = rsi_ma_series[rsi_ma_idx] if rsi_ma_idx < len(rsi_ma_series) else None
        ma_prev = rsi_ma_series[rsi_ma_idx - 1] if rsi_ma_idx - 1 >= 0 else None
        
        if None in [rsi_curr, rsi_prev, ma_curr, ma_prev]:
            continue
        
        # چک کراس روی همین کندل
        cross_up = rsi_prev < ma_prev and rsi_curr > ma_curr
        cross_down = rsi_prev > ma_prev and rsi_curr < ma_curr
        
        # شرط اصلی: همزمان روی همین کندل
        # 1. حجم این کندل بالا باشه
        # 2. RSI روی همین کندل کراس کرده باشه
        if vol_ratio_candle >= VOLUME_MULT and (cross_up or cross_down):
            print(f"  {symbol}: MATCH on candle -{i} | Vol {vol_ratio_candle:.2f}x | Cross {'UP' if cross_up else 'DOWN'}")
            return {
                "symbol": symbol,
                "price": closes[vol_idx],
                "vol_ratio": vol_ratio_candle,
                "rsi": rsi_curr,
                "rsi_ma": ma_curr,
                "direction": "up" if cross_up else "down",
                "candle_ago": i
            }
        
        # لاگ برای دیباگ
        print(f"  {symbol} candle-{i}: Vol {vol_ratio_candle:.2f}x {'OK' if vol_ratio_candle >= VOLUME_MULT else 'NO'} | RSI Cross {'OK' if (cross_up or cross_down) else 'NO'}")
    
    return None

# ===== اجرا =====
print(f"[{datetime.now().strftime('%H:%M:%S')}] بررسی {len(WATCHLIST)} ارز...")

signals = []
for symbol in WATCHLIST:
    try:
        result = check_symbol(symbol)
        if result:
            signals.append(result)
            print(f"  >> SIGNAL: {symbol}")
    except Exception as e:
        print(f"  {symbol}: error - {e}")

print(f"تعداد سیگنال: {len(signals)}")

for sig in signals:
    symbol = sig["symbol"].replace("USDT", "")
    if sig["direction"] == "up":
        emoji = "🟢"
        title = "سیگنال صعودی"
        action = "حجم بالا + RSI کراس به بالا (همزمان)"
    else:
        emoji = "🔴"
        title = "سیگنال نزولی"
        action = "حجم بالا + RSI کراس به پایین (همزمان)"
    
    ch5m = get_change(sig["symbol"], "5m", 1)
    ch15m = get_change(sig["symbol"], "15m", 1)
    ch1h = get_change(sig["symbol"], "1H", 1)
    
    # چند کندل پیش اتفاق افتاده
    if sig["candle_ago"] == 1:
        timing = "همین الان (آخرین کندل)"
    else:
        timing = f"{sig['candle_ago']} کندل پیش"
    
    msg = f"{emoji} <b>{title} — {symbol}</b> ({TIMEFRAME})\n\n"
    msg += f"{action}\n"
    msg += f"⏱ زمان: {timing}\n\n"
    msg += f"💰 قیمت: <b>${sig['price']:,.4f}</b>\n\n"
    msg += f"📊 <b>Volume:</b> <b>{sig['vol_ratio']:.2f}x</b> میانگین\n"
    msg += f"📈 <b>RSI:</b> <b>{sig['rsi']:.1f}</b> | MA: {sig['rsi_ma']:.1f}\n\n"
    msg += f"📉 <b>حرکت قیمت:</b>\n"
    msg += f"   • 5 دقیقه: {ch5m:+.2f}%\n"
    msg += f"   • 15 دقیقه: {ch15m:+.2f}%\n"
    msg += f"   • 1 ساعته: {ch1h:+.2f}%\n"
    msg += "\n💡 <i>برو پای چارت.</i>"
    
    send_telegram_message(msg)
