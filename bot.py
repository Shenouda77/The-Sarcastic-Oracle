import telebot
import os

# التوكن الخاص بك تم وضعه هنا
API_TOKEN = '8611847166:AAHsojGY1s0QDxRG5ALi4snPlCfNSv-CYoQ'

bot = telebot.TeleBot(API_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "🔮 Welcome to The Sarcastic Oracle! 🔮\n\n"
        "أهلاً بك في محراب العراف.. أنا هنا لحمايتك من الـ Rugpulls.\n"
        "هذا البوت كتب بمداد الثقة، وختم بكود الحرية. 🖋️🛡️\n\n"
        "قريباً.. سأكشف لك أسرار الشارت وأحذرك من النصابين."
    )
    bot.reply_to(message, welcome_text)

# سطر التشغيل الأساسي
if __name__ == "__main__":
    print("The Sarcastic Oracle is now ONLINE... 🐸🔮")
    bot.infinity_polling()
