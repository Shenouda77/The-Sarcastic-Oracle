import telebot
import time
import requests
import threading
import queue
import logging
from telebot import types
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- الإعدادات الأساسية ---
API_TOKEN ='8611847166:AAHsojGY1s0QDxRG5ALi4snPlCfNSv-CYoQ'
TWITTER_USER = "@OracleScans"
TWITTER_URL = "https://x.com/OracleScans"
BOT_LINK = "https://t.me/OracleOrigins_bot"

bot = telebot.TeleBot(API_TOKEN, threaded=True, num_threads=10)

# --- نظام الذاكرة المؤقتة ---
scan_cache = {}
CACHE_DURATION = 300
cache_lock = threading.Lock()

# --- نظام الطابور لمعالجة الطلبات الكثيرة ---
request_queue = queue.Queue(maxsize=500)

# --- حماية من السبام ---
user_cooldown = {}
COOLDOWN_SECONDS = 15
cooldown_lock = threading.Lock()

# --- إعداد جلسة الاتصال ---
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20))

# ════════════════════════════════════════
# API FETCHERS — مع Fallback كامل
# ════════════════════════════════════════

def fetch_rugcheck(ca_address):
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{ca_address}/report/summary"
        response = session.get(url, timeout=8)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"RugCheck error: {e}")
        return None

def fetch_dexscreener(ca_address):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{ca_address}"
        response = session.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if data.get('pairs') and len(data['pairs']) > 0:
                return data['pairs'][0]
        return None
    except Exception as e:
        logger.error(f"DexScreener error: {e}")
        return None

def fetch_goplus(ca_address):
    try:
        url = f"https://api.gopluslabs.io/api/v1/solana/token_security/{ca_address}"
        response = session.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if data.get('result'):
                keys = list(data['result'].keys())
                if keys:
                    return data['result'][keys[0]]
        return None
    except Exception as e:
        logger.error(f"GoPlus error: {e}")
        return None

# ════════════════════════════════════════
# نظام الكاش
# ════════════════════════════════════════

def get_from_cache(ca_address):
    with cache_lock:
        if ca_address in scan_cache:
            data, timestamp = scan_cache[ca_address]
            if time.time() - timestamp < CACHE_DURATION:
                return data
    return None

def save_to_cache(ca_address, data):
    with cache_lock:
        scan_cache[ca_address] = (data, time.time())
        # تنظيف الكاش القديم
        if len(scan_cache) > 1000:
            old_keys = [k for k, (_, t) in scan_cache.items()
                       if time.time() - t > CACHE_DURATION]
            for k in old_keys:
                del scan_cache[k]

# ════════════════════════════════════════
# حماية من السبام
# ════════════════════════════════════════

def is_on_cooldown(user_id):
    with cooldown_lock:
        now = time.time()
        if user_id in user_cooldown:
            if now - user_cooldown[user_id] < COOLDOWN_SECONDS:
                return True
        user_cooldown[user_id] = now
        return False

# ════════════════════════════════════════
# بناء التقرير الكامل
# ════════════════════════════════════════

def build_report(ca_address, rugcheck_data, dex_data, goplus_data):
    short_addr = f"{ca_address[:6]}...{ca_address[-4:]}"
    report = f"🛡️ *ORACLE SCAN REPORT* 🛡️\n\n"
    report += f"📍 `{short_addr}`\n"
    report += f"━━━━━━━━━━━━━━━━━\n\n"

    # --- RugCheck Score ---
    if rugcheck_data:
        score = rugcheck_data.get('score', 0)
        risks = rugcheck_data.get('risks', [])

        if score > 600:
            verdict = "🚨 HIGH RISK"
        elif score > 200:
            verdict = "⚠️ WARNING"
        else:
            verdict = "✅ SEEMS SAFE"

        report += f"📊 *Risk Score:* `{score}` — *{verdict}*\n\n"

        if risks:
            report += f"🔍 *Flags Detected:*\n"
            for r in risks[:4]:
                emoji = "🔴" if r.get('level') == 'danger' else "🟡"
                report += f"{emoji} {r.get('name', 'Unknown')}\n"
            report += "\n"
        else:
            report += f"✅ No critical flags detected\n\n"
    else:
        report += f"⚠️ *RugCheck:* Data unavailable\n\n"

    # --- GoPlus Honeypot ---
    if goplus_data:
        is_honeypot = goplus_data.get('honeypot') == '1' or goplus_data.get('cannot_sell_all') == '1'
        sell_tax = float(goplus_data.get('sell_tax', 0)) * 100
        buy_tax = float(goplus_data.get('buy_tax', 0)) * 100
        mintable = goplus_data.get('mintable') == '1'

        report += f"🧪 *Honeypot Test:*\n"
        if is_honeypot:
            report += f"🚨 *WARNING: HONEYPOT DETECTED*\n"
        report += f"• Buy Tax: {buy_tax:.1f}%{'  ⚠️' if buy_tax > 10 else ''}\n"
        report += f"• Sell Tax: {sell_tax:.1f}%{'  🚨' if sell_tax > 10 else ''}\n"
        report += f"• Mintable: {'⚠️ Yes' if mintable else '✅ No'}\n\n"

    # --- DexScreener Market Data ---
    if dex_data:
        price = dex_data.get('priceUsd', 'N/A')
        liq = dex_data.get('liquidity', {}).get('usd', 0)
        mcap = dex_data.get('marketCap', 0)
        volume = dex_data.get('volume', {}).get('h24', 0)
        change = dex_data.get('priceChange', {}).get('h24', None)

        def fmt(n):
            if not n: return "0"
            n = float(n)
            if n >= 1e6: return f"{n/1e6:.2f}M"
            if n >= 1e3: return f"{n/1e3:.1f}K"
            return f"{n:.2f}"

        liq_emoji = "🟢" if liq > 50000 else "🟡" if liq > 10000 else "🔴"

        report += f"💰 *Market Data:*\n"
        report += f"• Price: ${price}\n"
        report += f"• Liquidity: {liq_emoji} ${fmt(liq)}\n"
        if mcap: report += f"• Market Cap: ${fmt(mcap)}\n"
        if volume: report += f"• Volume 24h: ${fmt(volume)}\n"
        if change is not None:
            ch = float(change)
            report += f"• Change 24h: {'📈 +' if ch >= 0 else '📉 '}{ch:.1f}%\n"

        report += f"\n📊 [Chart](https://dexscreener.com/solana/{ca_address})\n\n"
    else:
        report += f"📊 *Market Data:* Not listed yet\n\n"

    # --- Final Verdict ---
    report += f"━━━━━━━━━━━━━━━━━\n"

    is_honeypot = goplus_data and (goplus_data.get('honeypot') == '1' or goplus_data.get('cannot_sell_all') == '1')
    high_risk = rugcheck_data and rugcheck_data.get('score', 0) > 600
    medium_risk = rugcheck_data and rugcheck_data.get('score', 0) > 200

    if is_honeypot:
        report += f"🚨 *AVOID — Honeypot. You cannot sell.*\n"
    elif high_risk:
        report += f"🔴 *HIGH RISK — Multiple red flags.*\n"
    elif medium_risk:
        report += f"🟡 *MEDIUM RISK — Proceed with caution.*\n"
    else:
        report += f"🟢 *RELATIVELY SAFE — Always DYOR.*\n"

    report += f"\n_🔮 @OracleScans — I don't predict. I expose._"
    return report

# ════════════════════════════════════════
# معالجة السكان الرئيسية
# ════════════════════════════════════════

def process_scan(chat_id, message_id, ca_address):
    try:
        # تحقق من الكاش أولاً
        cached = get_from_cache(ca_address)
        if cached:
            report, rugcheck, dex, goplus = cached
            final_report = build_report(ca_address, rugcheck, dex, goplus)
            bot.edit_message_text(
                final_report, chat_id=chat_id,
                message_id=message_id,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return

        # جلب البيانات من APIs
        rugcheck = fetch_rugcheck(ca_address)
        dex = fetch_dexscreener(ca_address)
        goplus = fetch_goplus(ca_address)

        # لو كل الـ APIs فشلوا
        if not rugcheck and not dex and not goplus:
            bot.edit_message_text(
                "⚠️ *Oracle is searching deeper...*\n\n"
                "This contract is very fresh or not indexed yet.\n"
                "Try again in 2 minutes.\n\n"
                "_🔮 @OracleScans_",
                chat_id=chat_id,
                message_id=message_id,
                parse_mode='Markdown'
            )
            return

        # بناء التقرير
        final_report = build_report(ca_address, rugcheck, dex, goplus)

        # حفظ في الكاش
        save_to_cache(ca_address, (final_report, rugcheck, dex, goplus))

        bot.edit_message_text(
            final_report, chat_id=chat_id,
            message_id=message_id,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"process_scan error: {e}")
        try:
            bot.edit_message_text(
                "❌ Analysis failed. Please try again.",
                chat_id=chat_id,
                message_id=message_id
            )
        except:
            pass

# ════════════════════════════════════════
# معالج الطابور
# ════════════════════════════════════════

def queue_worker():
    while True:
        try:
            item = request_queue.get(timeout=1)
            if item:
                chat_id, message_id, ca_address = item
                process_scan(chat_id, message_id, ca_address)
                request_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Queue worker error: {e}")

# ════════════════════════════════════════
# أوامر البوت
# ════════════════════════════════════════

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    btn_check = types.InlineKeyboardButton("🔍 Scan Contract", callback_data="check_ca")
    btn_twitter = types.InlineKeyboardButton("🐦 Follow The Oracle", url=TWITTER_URL)
    markup.add(btn_check)
    markup.add(btn_twitter)

    welcome_text = (
        "🔮 *The Sarcastic Oracle | Origins* 🔮\n\n"
        "I don't predict markets.\n"
        "I expose them.\n\n"
        "Send any Solana contract address.\n"
        "The truth will follow.\n\n"
        "_Too late for me. Not too late for you._"
    )
    bot.send_message(
        message.chat.id, welcome_text,
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "🔮 *Oracle Help*\n\n"
        "Send any Solana contract address directly.\n\n"
        "The report includes:\n"
        "🛡 Security Score\n"
        "🧪 Honeypot Test\n"
        "💰 Market Data\n"
        "⚖️ Final Verdict\n\n"
        "_Not financial advice. Always DYOR._\n\n"
        f"🐦 Follow: {TWITTER_URL}"
    )
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "check_ca":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📥 *Drop the Solana contract address below:*",
            parse_mode='Markdown'
        )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    ca_address = message.text.strip()

    # تحقق من صحة العنوان
    if not (32 <= len(ca_address) <= 44):
        bot.reply_to(
            message,
            "⚠️ *Invalid address.*\n\nSolana addresses are 32–44 characters.\nSend a valid contract address.",
            parse_mode='Markdown'
        )
        return

    import re
    if not re.match(r'^[1-9A-HJ-NP-Za-km-z]+$', ca_address):
        bot.reply_to(message, "⚠️ *Invalid format.* Send a Base58 Solana address.")
        return

    # تحقق من الكولداون
    if is_on_cooldown(message.from_user.id):
        bot.reply_to(
            message,
            "⏳ *Please wait 15 seconds before scanning again.*",
            parse_mode='Markdown'
        )
        return

    # إرسال رسالة الانتظار
    processing_msg = bot.reply_to(
        message,
        "🔮 *Consulting the ancient scrolls...*\n_Scanning for traps and rugs..._",
        parse_mode='Markdown'
    )

    # إضافة للطابور
    try:
        request_queue.put_nowait(
            (processing_msg.chat.id, processing_msg.message_id, ca_address)
        )
    except queue.Full:
        bot.edit_message_text(
            "⚠️ Oracle is busy. Please try again in a moment.",
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id
        )

# ════════════════════════════════════════
# تشغيل البوت
# ════════════════════════════════════════

if __name__ == "__main__":
    # تشغيل 5 workers للطابور
    for i in range(5):
        worker = threading.Thread(target=queue_worker, daemon=True)
        worker.start()
        logger.info(f"Worker {i+1} started")

    logger.info("🔮 The Oracle is now online...")
    print("🔮 The Oracle is now online...")

    bot.infinity_polling(timeout=60, long_polling_timeout=60)

