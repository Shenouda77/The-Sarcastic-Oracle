import telebot
import time
import requests
from telebot import types
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- الإعدادات الأساسية ---
API_TOKEN = '8611847166:AAHsojGY1s0QDxRG5ALi4snPlCfNSv-CYoQ'
TWITTER_USER = "@OracleScans"
TWITTER_URL = "https://x.com/OracleScans"

bot = telebot.TeleBot(API_TOKEN)

# --- نظام الذاكرة المؤقتة (Caching) لتقليل الضغط ---
scan_cache = {}
CACHE_DURATION = 300  # 5 دقائق

# --- إعداد جلسة الاتصال لتجنب الـ Rate Limits ---
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def get_rugcheck_report(ca_address):
    # التأكد إذا كانت النتيجة موجودة في الذاكرة لتوفير الطلبات
    current_time = time.time()
    if ca_address in scan_cache:
        cached_data, timestamp = scan_cache[ca_address]
        if current_time - timestamp < CACHE_DURATION:
            return cached_data

    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{ca_address}/report/summary"
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # حفظ النتيجة في الذاكرة
            scan_cache[ca_address] = (data, current_time)
            return data
        return None
    except:
        return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    btn_check = types.InlineKeyboardButton("🔍 Scan Contract", callback_data="check_ca")
    btn_twitter = types.InlineKeyboardButton("🐦 Follow The Oracle", url=TWITTER_URL)
    markup.add(btn_check)
    markup.add(btn_twitter)

    welcome_text = (
        "🔮 **The Sarcastic Oracle | Origins** 🔮\n\n"
        "Welcome to the inner circle. I decode the blockchain ink to save your $SOL from the abyss.\n\n"
        "**Are you ready to see the truth?**"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "check_ca":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📥 **Drop the Solana CA below. Let the ink flow:**")

@bot.message_handler(func=lambda message: True)
def handle_ca(message):
    ca_address = message.text.strip()
    
    if 32 <= len(ca_address) <= 44:
        processing_msg = bot.reply_to(message, "🖋️ **Consulting the ancient scrolls...**\n*Scanning for traps and rugs...*", parse_mode='Markdown')
        
        data = get_rugcheck_report(ca_address)
        
        if data:
            risk_score = data.get('score', 0)
            risks = data.get('risks', [])
            
            risk_details = ""
            for r in risks[:4]:
                level_emoji = "🔴" if r['level'] == 'danger' else "🟡"
                risk_details += f"{level_emoji} {r['name']}\n"
            
            # تحديد الحالة بناءً على السكور
            if risk_score > 600:
                status = "🚨 DEADLY RUG"
            elif risk_score > 200:
                status = "⚠️ WARNING"
            else:
                status = "✅ SEEMS SAFE"
            
            result_text = (
                f"🛡️ **ORACLE SCAN REPORT** 🛡️\n\n"
                f"📍 **Address:** `{ca_address}`\n"
                f"📊 **Risk Score:** `{risk_score}`\n"
                f"⚖️ **Verdict:** **{status}**\n\n"
                f"🔍 **Analysis:**\n{risk_details if risk_details else 'The code looks clean... for now.'}\n\n"
                f"--- \n"
                f"🖋️ **Join the Elite:** {TWITTER_URL}\n"
                f"🐸 *Don't get rugged. Follow {TWITTER_USER}*"
            )
        else:
            result_text = "❌ **Oracle Blinded:** Data unavailable. The contract might be too fresh or hidden in the shadows."
            
        bot.edit_message_text(result_text, chat_id=processing_msg.chat.id, message_id=processing_msg.message_id, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        bot.reply_to(message, "⚠️ **Invalid Scroll.** Send a real Solana Address.")

if __name__ == "__main__":
    print("🔮 The Oracle is now online...")
    bot.infinity_polling()

