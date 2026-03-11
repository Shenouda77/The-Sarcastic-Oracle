import telebot
import time
import requests
from telebot import types

# Your Bot Token
API_TOKEN = '8611847166:AAHsojGY1s0QDxRG5ALi4snPlCfNSv-CYoQ'
bot = telebot.TeleBot(API_TOKEN)

# 🔮 Function to get REAL DATA from RugCheck
def get_rugcheck_report(ca_address):
    try:
        url = f"https://api.rugcheck.xyz/v1/tokens/{ca_address}/report/summary"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    btn_check = types.InlineKeyboardButton("🔍 Check Contract Address", callback_data="check_ca")
    markup.add(btn_check)

    welcome_text = (
        "🔮 **The Sarcastic Oracle | Origins** 🔮\n\n"
        "Solana's ultimate truth-seeker. I scan the ink to reveal the code.\n\n"
        "Click below to scan a contract:"
    )
    bot.reply_to(message, welcome_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "check_ca":
        bot.send_message(call.message.chat.id, "📥 **Send the Solana CA now:**")

@bot.message_handler(func=lambda message: True)
def handle_ca(message):
    ca_address = message.text.strip()
    
    if 32 <= len(ca_address) <= 44:
        processing_msg = bot.reply_to(message, "🔍 **Analyzing Blockchain Data...**\n*Querying RugCheck for security risks...*", parse_mode='Markdown')
        
        # Real Analysis from RugCheck
        data = get_rugcheck_report(ca_address)
        time.sleep(2) # Natural delay
        
        if data:
            risk_score = data.get('score', 'Unknown')
            risks = data.get('risks', [])
            
            risk_details = ""
            for r in risks[:3]: # Show top 3 risks
                risk_details += f"• {r['name']}: {r['level']}\n"
            
            status = "❌ DANGER" if risk_score > 500 else "✅ SEEMS SAFE"
            
            result_text = (
                f"🛡️ **ORACLE SCAN REPORT** 🛡️\n\n"
                f"📍 **Address:** `{ca_address}`\n"
                f"📊 **Risk Score:** `{risk_score}`\n"
                f"⚖️ **Verdict:** **{status}**\n\n"
                f"🔍 **Found Risks:**\n{risk_details if risk_details else 'None found.'}\n"
                "\n*The Oracle has spoken. Follow the ink.* 🖋️"
            )
        else:
            result_text = "❌ **Error:** Could not fetch data for this contract. It might be too new or invalid."
            
        bot.edit_message_text(result_text, chat_id=processing_msg.chat.id, message_id=processing_msg.message_id, parse_mode='Markdown')
    else:
        bot.reply_to(message, "⚠️ Invalid Address.")

if __name__ == "__main__":
    bot.infinity_polling()
