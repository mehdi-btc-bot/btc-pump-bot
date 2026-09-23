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

TIMEFRAME = "5m"
VOLUME_MA_PERIOD = 20
VOLUME_MULT = 1.3           # حجم باید 1.3x MA باشه
FRACTAL_MODE = "3"
USE_BODY = True
FVG_FILTER = True
FVG_DISTANCE = 3
RECENT_BARS = 20            # OB باید توی 20 کندل اخیر باشه
PROXIMITY_PCT = 0.5         # فاصله نزدیکی به OB (درصد)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("Telegram sent")
    except Exception as e:
        print(f"TG error: {e}")

def get_klines(symbol, interval, limit=300):
    try:
        inst = symbol.replace('USDT', '-USDT')
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={interval}&limit={limit}"
        r = requests.get(url, timeout=10).json()
        if r.get("code") != "0":
            return None
        return list(reversed(r["data"]))
    except Exception as e:
        print(f"get_klines error: {e}")
        return None

def calculate_ma(values, period):
    if len(values) < period:
        return None
    return [sum(values[i-period+1:i+1]) / period for i in range(period-1, len(values))]

def is_fractal_high(klines, i, mode="3"):
    if mode == "3":
        if i + 3 >= len(klines):
            return False
        h1 = float(klines[i+1][2])
        h0 = float(klines[i][2])
        h2 = float(klines[i+2][2])
        h3 = float(klines[i+3][2])
        return h0 < h1 and (h2 < h1 or (h2 == h1 and h3 < h2))
    else:
        if i + 5 >= len(klines):
            return False
        h0 = float(klines[i][2])
        h1 = float(klines[i+1][2])
        h2 = float(klines[i+2][2])
        h3 = float(klines[i+3][2])
        h4 = float(klines[i+4][2])
        return h0 < h2 and h1 < h2 and h3 < h2 and h4 < h2

def is_fractal_low(klines, i, mode="3"):
    if mode == "3":
        if i + 3 >= len(klines):
            return False
        l1 = float(klines[i+1][3])
        l0 = float(klines[i][3])
        l2 = float(klines[i+2][3])
        l3 = float(klines[i+3][3])
        return l0 > l1 and (l2 > l1 or (l2 == l1 and l3 > l2))
    else:
        if i + 5 >= len(klines):
            return False
        l0 = float(klines[i][3])
        l1 = float(klines[i+1][3])
        l2 = float(klines[i+2][3])
        l3 = float(klines[i+3][3])
        l4 = float(klines[i+4][3])
        return l0 > l2 and l1 > l2 and l3 > l2 and l4 > l2

def find_bearish_ob(klines, fractal_low_idx, fractal_low_price, mode="3", use_body=True, filter_fvg=True, fvg_distance=3):
    n = len(klines) - 1
    max_high = float('-inf')
    ob_idx = None
    gap_idx = None
    
    for k in range(n - 1, fractal_low_idx, -1):
        o = float(klines[k][1])
        h = float(klines[k][2])
        c = float(klines[k][4])
        
        if c > o and h > max_high:
            ob_idx = k
            max_high = h
        
        if k + 2 <= n:
            c1 = float(klines[k+1][4])
            l2 = float(klines[k+2][3])
            if c1 < l2:
                gap_idx = k + 2
    
    if ob_idx is None:
        return None
    
    if filter_fvg:
        if gap_idx is None:
            return None
        if not (0 <= ob_idx - gap_idx <= fvg_distance):
            return None
    
    candle = klines[ob_idx]
    o = float(candle[1])
    h = float(candle[2])
    l = float(candle[3])
    
    if use_body:
        btm = min(o, float(candle[4]))
    else:
        btm = l
    
    return {"type": "bearish", "top": h, "btm": btm, "idx": ob_idx}

def find_bullish_ob(klines, fractal_high_idx, fractal_high_price, mode="3", use_body=True, filter_fvg=True, fvg_distance=3):
    n = len(klines) - 1
    min_low = float('inf')
    ob_idx = None
    gap_idx = None
    
    for k in range(n - 1, fractal_high_idx, -1):
        o = float(klines[k][1])
        h = float(klines[k][2])
        l = float(klines[k][3])
        c = float(klines[k][4])
        
        if c < o and l < min_low:
            ob_idx = k
            min_low = l
        
        if k + 2 <= n:
            c1 = float(klines[k+1][4])
            h2 = float(klines[k+2][2])
            if c1 > h2:
                gap_idx = k + 2
    
    if ob_idx is None:
        return None
    
    if filter_fvg:
        if gap_idx is None:
            return None
        if not (0 <= ob_idx - gap_idx <= fvg_distance):
            return None
    
    candle = klines[ob_idx]
    o = float(candle[1])
    h = float(candle[2])
    l = float(candle[3])
    
    if use_body:
        top = max(o, float(candle[4]))
    else:
        top = h
    
    return {"type": "bullish", "top": top, "btm": l, "idx": ob_idx}

def check_symbol(symbol):
    klines = get_klines(symbol, TIMEFRAME, 300)
    if not klines or len(klines) < 100:
        return None
    
    current_price = float(klines[-1][4])
    n = len(klines) - 1
    
    volumes = [float(k[5]) for k in klines]
    vol_ma_series = calculate_ma(volumes, VOLUME_MA_PERIOD)
    if not vol_ma_series:
        return None
    
    # ===== شرط 1: حجم کندل فعلی ≥ 1.3x MA =====
    current_vol = volumes[-1]
    current_vol_ma = vol_ma_series[-1]
    vol_ratio = current_vol / current_vol_ma if current_vol_ma > 0 else 0
    
    if vol_ratio < VOLUME_MULT:
        return None
    
    # ===== شرط 2: OB فعال (تازه + قیمت نزدیک) =====
    recent_obs = []
    for i in range(max(0, n - 30), n):
        if is_fractal_high(klines, i, FRACTAL_MODE):
            fh_price = float(klines[i+1][2]) if FRACTAL_MODE == "3" else float(klines[i+2][2])
            fh_idx = i + 1 if FRACTAL_MODE == "3" else i + 2
            
            for j in range(fh_idx + 1, n + 1):
                if float(klines[j][4]) > fh_price:
                    ob = find_bullish_ob(klines, fh_idx, fh_price, FRACTAL_MODE, USE_BODY, FVG_FILTER, FVG_DISTANCE)
                    if ob and ob["idx"] >= n - RECENT_BARS:
                        recent_obs.append(ob)
                    break
        
        if is_fractal_low(klines, i, FRACTAL_MODE):
            fl_price = float(klines[i+1][3]) if FRACTAL_MODE == "3" else float(klines[i+2][3])
            fl_idx = i + 1 if FRACTAL_MODE == "3" else i + 2
            
            for j in range(fl_idx + 1, n + 1):
                if float(klines[j][4]) < fl_price:
                    ob = find_bearish_ob(klines, fl_idx, fl_price, FRACTAL_MODE, USE_BODY, FVG_FILTER, FVG_DISTANCE)
                    if ob and ob["idx"] >= n - RECENT_BARS:
                        recent_obs.append(ob)
                    break
    
    if not recent_obs:
        return None
    
    # چک نزدیکی قیمت به نزدیک‌ترین OB
    nearby_obs = []
    for ob in recent_obs:
        ob_top = ob["top"]
        ob_btm = ob["btm"]
        
        # داخل OB
        if ob_btm <= current_price <= ob_top:
            nearby_obs.append(ob)
        # نزدیک OB
        elif ob_top < current_price and (current_price - ob_top) / ob_top * 100 <= PROXIMITY_PCT:
            nearby_obs.append(ob)
        elif ob_btm > current_price and (ob_btm - current_price) / current_price * 100 <= PROXIMITY_PCT:
            nearby_obs.append(ob)
    
    if not nearby_obs:
        return None
    
    latest_ob = nearby_obs[-1]
    
    return {
        "symbol": symbol,
        "price": current_price,
        "type": latest_ob["type"],
        "ob_top": latest_ob["top"],
        "ob_btm": latest_ob["btm"],
        "vol_ratio": vol_ratio,
        "vol_current": current_vol,
        "vol_ma": current_vol_ma
    }

print(f"[{datetime.now().strftime('%H:%M:%S')}] بررسی {len(WATCHLIST)} ارز برای OB + حجم...")

signals = []
for symbol in WATCHLIST:
    try:
        r = check_symbol(symbol)
        if r:
            signals.append(r)
            print(f"  >> {symbol}: {r['type']} OB (Vol {r['vol_ratio']:.2f}x)")
    except Exception as e:
        print(f"  {symbol}: {e}")

print(f"تعداد سیگنال: {len(signals)}")

for sig in signals:
    symbol = sig["symbol"].replace("USDT", "")
    
    if sig["type"] == "bullish":
        emoji = "🟢"
        title = "Bullish OB — حمایت"
        action = "حجم بالای MA + قیمت داخل/نزدیک OB حمایت"
    else:
        emoji = "🔴"
        title = "Bearish OB — مقاومت"
        action = "حجم بالای MA + قیمت داخل/نزدیک OB مقاومت"
    
    msg = f"{emoji} <b>{title} — {symbol}</b>\n"
    msg += f"⏱ {datetime.now().strftime('%H:%M:%S')}\n\n"
    msg += f"💰 قیمت: <b>${sig['price']:,.4f}</b>\n\n"
    msg += f"📦 <b>Order Block:</b>\n"
    msg += f"   • محدوده: ${sig['ob_btm']:,.4f} — ${sig['ob_top']:,.4f}\n\n"
    msg += f"✅ <b>تأییدها:</b>\n"
    msg += f"   • حجم: <b>{sig['vol_ratio']:.2f}x</b> MA\n"
    msg += f"   • OB تازه فعال\n\n"
    msg += f"💡 <i>برو پای چارت و تأیید کن.</i>"
    
    send_telegram_message(msg)
