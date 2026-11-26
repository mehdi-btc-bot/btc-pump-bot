import os
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

WATCHLIST = [
    "TRBUSDT", "ETCUSDT", "APTUSDT", "FARTCOINUSDT", "TAOUSDT", 
    "OPUSDT", "LDOUSDT", "HYPEUSDT", "AVAXUSDT", "DOGEUSDT", 
    "ADAUSDT", "LINKUSDT", "ZECUSDT", "INJUSDT", "AAVEUSDT",
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BCHUSDT", "LTCUSDT", 
    "XRPUSDT", "XLMUSDT", "BNBUSDT", "UNIUSDT", "SUIUSDT"
]

TIMEFRAME = "15m"
CHECK_INTERVAL_SECONDS = 60 * 15  # هر ۱۵ دقیقه اسکن میکنه
RSI_LEN = 14
RSI_SMA_LEN = 14
VP_PERIOD = 300
VP_BINS = 100

# ذخیره زمان آخرین آلارم در حافظه ربات
last_alerts = {}

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

def get_binance_data(symbol, interval, limit=500):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base_vol', 'taker_quote_vol', 'ignore'])
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_volume_profile_poc(df, period=300, bins=100):
    recent_df = df.tail(period)
    max_price = recent_df['high'].max()
    min_price = recent_df['low'].min()
    
    if max_price == min_price:
        return None, None, None
    
    step = (max_price - min_price) / bins
    vol_bins = np.zeros(bins)
    
    for _, row in recent_df.iterrows():
        close_p, vol = row['close'], row['volume']
        for j in range(bins):
            lower = min_price + step * j
            upper = lower + step
            if close_p <= upper + step*1.5 and close_p >= lower - step*1.5:
                vol_bins[j] += vol
                
    poc_index = np.argmax(vol_bins)
    poc_price = min_price + (step * poc_index) + (step / 2)
    ob_high = poc_price + step
    ob_low = poc_price - step
    return poc_price, ob_high, ob_low

def check_signals():
    for symbol in WATCHLIST:
        try:
            df = get_binance_data(symbol, TIMEFRAME, limit=500)
            if df is None or len(df) < 20:
                continue
                
            df['rsi'] = calculate_rsi(df, RSI_LEN)
            df['rsi_sma'] = df['rsi'].rolling(window=RSI_SMA_LEN).mean()
            
            last_rsi = df['rsi'].iloc[-2]
            last_sma = df['rsi_sma'].iloc[-2]
            curr_rsi = df['rsi'].iloc[-1]
            curr_sma = df['rsi_sma'].iloc[-1]
            
            rsi_cross = False
            if not pd.isna(last_rsi) and not pd.isna(last_sma):
                if last_rsi < last_sma and curr_rsi > curr_sma:
                    rsi_cross = True
                    
            poc_price, ob_high, ob_low = calculate_volume_profile_poc(df, VP_PERIOD, VP_BINS)
            
            if poc_price is not None:
                current_price = df['close'].iloc[-1]
                current_high = df['high'].iloc[-1]
                current_low = df['low'].iloc[-1]
                
                touch_poc = current_low <= poc_price <= current_high
                
                if rsi_cross and touch_poc:
                    now = time.time()
                    if symbol not in last_alerts or (now - last_alerts[symbol]) > 1800: # 30 دقیقه
                        
                        msg = f"🟢 <b>Bullish OB — حمایت — {symbol.replace('USDT', '')}</b>\n"
                        msg += f"⏱ <i>{datetime.now().strftime('%H:%M:%S')}</i>\n\n"
                        msg += f"💰 <b>قیمت:</b> {current_price:.4f}$\n\n"
                        msg += f"📦 <b>Order Block:</b>\n"
                        msg += f"• محدوده: {ob_high:.4f}$ — {ob_low:.4f}$\n\n"
                        msg += f"✅ <b>تاییدها:</b>\n"
                        msg += f"• حجم کراس RSI: فعال\n"
                        msg += f"• قیمت داخل/نزدیک POC (خط زرد)\n\n"
                        msg += f"💡 برو پای چارت و تایید کن."
                        
                        send_telegram_message(msg)
                        last_alerts[symbol] = now
                        print(f"Signal sent for {symbol}")
                        
        except Exception as e:
            print(f"Error checking {symbol}: {e}")

if __name__ == "__main__":
    print("Bot is starting on Render...")
    # پیام تستی اولیه
    send_telegram_message("✅ ربات روی سرور Render روشن شد و هر ۱۵ دقیقه بازار را رصد می‌کند.")
    
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning market...")
        check_signals()
        time.sleep(CHECK_INTERVAL_SECONDS)
