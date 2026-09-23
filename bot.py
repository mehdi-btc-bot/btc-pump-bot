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

TIMEFRAME = "15m"
DEPTH = 2                       # Intermediate Term
SHOW_BULL = 3                   # چند تا Bullish OB چک کن
SHOW_BEAR = 3                   # چند تا Bearish OB چک کن
USE_BODY = True                 # از body کندل استفاده کن
PROXIMITY_PCT = 0.3             # فاصله نزدیک به OB (درصد)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("Telegram sent")
    except Exception as e:
        print(f"TG error: {e}")

def get_klines(symbol, interval, limit=200):
    try:
        inst = symbol.replace('USDT', '-USDT')
        url = f"https://www.okx.com/api/v5/market/candles?instId={inst}&bar={interval}&limit={limit}"
        r = requests.get(url, timeout=10).json()
        if r.get("code") != "0":
            return None
        # OKX: [ts, open, high, low, close, vol, ...]
        return list(reversed(r["data"]))
    except:
        return None

def detect_swings(klines, depth):
    """تشخیص Swing High/Low"""
    highs = [float(k[2]) for k in klines]
    lows = [float(k[3]) for k in klines]
    
    swing_highs = []
    swing_lows = []
    
    for i in range(depth, len(klines) - depth):
        is_high = all(highs[i] >= highs[i-j] for j in range(1, depth+1)) and \
                  all(highs[i] >= highs[i+j] for j in range(1, depth+1))
        is_low = all(lows[i] <= lows[i-j] for j in range(1, depth+1)) and \
                 all(lows[i] <= lows[i+j] for j in range(1, depth+1))
        
        if is_high:
            swing_highs.append({"idx": i, "price": highs[i]})
        if is_low:
            swing_lows.append({"idx": i, "price": lows[i]})
    
    return swing_highs, swing_lows

def find_bullish_obs(klines, swing_highs, use_body=True):
    """پیدا کردن Bullish Order Blocks"""
    obs = []
    n = len(klines) - 1
    
    for sh in swing_highs:
        sh_idx = sh["idx"]
        sh_price = sh["price"]
        
        # چک کن که قیمت از Swing High رد شده بالا
        # یعنی بعد از swing، close ای بالاتر از sh_price داریم
        breakout_idx = None
        for i in range(sh_idx + 1, n + 1):
            if float(klines[i][4]) > sh_price:
                breakout_idx = i
                break
        
        if breakout_idx is None:
            continue
        
        # از swing تا breakout، کندل با کمترین low رو پیدا کن
        min_low = float('inf')
        min_idx = None
        for i in range(sh_idx, breakout_idx):
            low_i = float(klines[i][3])
            if low_i < min_low:
                min_low = low_i
                min_idx = i
        
        if min_idx is None:
            continue
        
        # ناحیه OB
        candle = klines[min_idx]
        if use_body:
            top = max(float(candle[1]), float(candle[4]))  # max(open, close)
        else:
            top = float(candle[2])  # high
        
        btm = float(candle[3])  # low
        
        obs.append({
            "top": top,
            "btm": btm,
            "idx": min_idx,
            "time": candle[0]
        })
    
    return obs

def find_bearish_obs(klines, swing_lows, use_body=True):
    """پیدا کردن Bearish Order Blocks"""
    obs = []
    n = len(klines) - 1
    
    for sl in swing_lows:
        sl_idx = sl["idx"]
        sl_price = sl["price"]
        
        # چک کن که قیمت از Swing Low رد شده پایین
        breakout_idx = None
        for i in range(sl_idx + 1, n + 1):
            if float(klines[i][4]) < sl_price:
                breakout_idx = i
                break
        
        if breakout_idx is None:
            continue
        
        # از swing تا breakout، کندل با بیشترین high رو پیدا کن
        max_high = float('-inf')
        max_idx = None
        for i in range(sl_idx, breakout_idx):
            high_i = float(klines[i][2])
            if high_i > max_high:
                max_high = high_i
                max_idx = i
        
        if max_idx is None:
            continue
        
        # ناحیه OB
        candle = klines[max_idx]
        if use_body:
            btm = min(float(candle[1]), float(candle[4]))  # min(open, close)
        else:
            btm = float(candle[3])  # low
        
        top = float(candle[2])  # high
        
        obs.append({
            "top": top,
            "btm": btm,
            "idx": max_idx,
            "time": candle[0]
        })
    
    return obs

def check_proximity(current_price, obs, proximity_pct):
    """چک کن که قیمت نزدیک کدوم OB هست"""
    nearby = []
    for ob in obs:
        top = ob["top"]
        btm = ob["btm"]
        
        # اگه قیمت داخل OB باشه
        if btm <= current_price <= top:
            nearby.append({
                "type": "inside",
                "ob": ob
            })
        # اگه قیمت بالای OB باشه و نزدیک
        elif top < current_price and (current_price - top) / top * 100 <= proximity_pct:
            nearby.append({
                "type": "above",
                "ob": ob,
                "distance": (current_price - top) / top * 100
            })
        # اگه قیمت زیر OB باشه و نزدیک
        elif btm > current_price and (btm - current_price) / current_price * 100 <= proximity_pct:
            nearby.append({
                "type": "below",
                "ob": ob,
                "distance": (btm - current_price) / current_price * 100
            })
    
    return nearby

def check_symbol(symbol):
    klines = get_klines(symbol, TIMEFRAME, 200)
    if not klines or len(klines) < 50:
        return None
    
    current_price = float(klines[-1][4])
    
    swing_highs, swing_lows = detect_swings(klines, DEPTH)
    
    if not swing_highs or not swing_lows:
        return None
    
    bullish_obs = find_bullish_obs(klines, swing_highs, USE_BODY)
    bearish_obs = find_bearish_obs(klines, swing_lows, USE_BODY)
    
    # آخرین N تا
    bullish_obs = bullish_obs[-SHOW_BULL:] if len(bullish_obs) > SHOW_BULL else bullish_obs
    bearish_obs = bearish_obs[-SHOW_BEAR:] if len(bearish_obs) > SHOW_BEAR else bearish_obs
    
    # چک نزدیکی
    bull_nearby = check_proximity(current_price, bullish_obs, PROXIMITY_PCT)
    bear_nearby = check_proximity(current_price, bearish_obs, PROXIMITY_PCT)
    
    return {
        "symbol": symbol,
        "price": current_price,
        "bull_nearby": bull_nearby,
        "bear_nearby": bear_nearby,
        "bull_count": len(bullish_obs),
        "bear_count": len(bearish_obs)
    }

print(f"[{datetime.now().strftime('%H:%M:%S')}] بررسی {len(WATCHLIST)} ارز برای Order Block...")

alerts = []
for symbol in WATCHLIST:
    try:
        r = check_symbol(symbol)
        if r and (r["bull_nearby"] or r["bear_nearby"]):
            alerts.append(r)
            print(f"  >> {symbol}: نزدیک OB! ({len(r['bull_nearby'])} bullish, {len(r['bear_nearby'])} bearish)")
    except Exception as e:
        print(f"  {symbol}: {e}")

print(f"تعداد هشدار OB: {len(alerts)}")

for a in alerts:
    symbol = a["symbol"].replace("USDT", "")
    price = a["price"]
    
    msg = f"📦 <b>Order Block Alert — {symbol}</b>\n"
    msg += f"⏱ {datetime.now().strftime('%H:%M:%S')}\n\n"
    msg += f"💰 قیمت فعلی: <b>${price:,.4f}</b>\n\n"
    
    if a["bull_nearby"]:
        msg += "🟢 <b>نزدیک Bullish OB (حمایت):</b>\n"
        for n in a["bull_nearby"]:
            ob = n["ob"]
            if n["type"] == "inside":
                msg += f"   • <b>داخل OB</b>: ${ob['btm']:,.4f} — ${ob['top']:,.4f}\n"
            elif n["type"] == "above":
                msg += f"   • بالای OB ({n['distance']:.2f}% فاصله): ${ob['btm']:,.4f} — ${ob['top']:,.4f}\n"
            else:
                msg += f"   • زیر OB ({n['distance']:.2f}% فاصله): ${ob['btm']:,.4f} — ${ob['top']:,.4f}\n"
        msg += "\n"
    
    if a["bear_nearby"]:
        msg += "🔴 <b>نزدیک Bearish OB (مقاومت):</b>\n"
        for n in a["bear_nearby"]:
            ob = n["ob"]
            if n["type"] == "inside":
                msg += f"   • <b>داخل OB</b>: ${ob['btm']:,.4f} — ${ob['top']:,.4f}\n"
            elif n["type"] == "above":
                msg += f"   • بالای OB ({n['distance']:.2f}% فاصله): ${ob['btm']:,.4f} — ${ob['top']:,.4f}\n"
            else:
                msg += f"   • زیر OB ({n['distance']:.2f}% فاصله): ${ob['btm']:,.4f} — ${ob['top']:,.4f}\n"
    
    msg += "\n💡 <i>برو پای چارت و واکنش قیمت رو ببین.</i>"
    
    send_telegram_message(msg)
