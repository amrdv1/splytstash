import telebot
import time
import sqlite3
import os
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("Bot token is not defined")
SUPER_ADMIN = 1669340183
print("TOKEN:", TOKEN)
bot = telebot.TeleBot(TOKEN)

#база
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS admins (id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS banned (id INTEGER)")
conn.commit()


def get_admins():
    cursor.execute("SELECT id FROM admins")
    admins = {row[0] for row in cursor.fetchall()}
    admins.add(SUPER_ADMIN)
    return admins


def get_banned():
    cursor.execute("SELECT id FROM banned")
    return {row[0] for row in cursor.fetchall()}

user_messages = {}


@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id in get_banned():
        return
    bot.send_message(message.chat.id, "Привіт,сюди ви можете надсилати свої демки, меми, питання та пропозиції,які будуть відправлені адміністраторам.")


@bot.message_handler(commands=['addadmin'])
def add_admin(message):
    if message.from_user.id == SUPER_ADMIN:
        try:
            new_admin = int(message.text.split()[1])
            cursor.execute("INSERT INTO admins VALUES (?)", (new_admin,))
            conn.commit()
            bot.send_message(message.chat.id, "✅ Адмін доданий")
        except:
            bot.send_message(message.chat.id, "❌ /addadmin ID")


@bot.message_handler(commands=['removeadmin'])
def remove_admin(message):
    if message.from_user.id == SUPER_ADMIN:
        try:
            admin_id = int(message.text.split()[1])
            cursor.execute("DELETE FROM admins WHERE id=?", (admin_id,))
            conn.commit()
            bot.send_message(message.chat.id, "❌ Адмін видалений")
        except:
            bot.send_message(message.chat.id, "❌ /removeadmin ID")


@bot.message_handler(commands=['admins'])
def admins(message):
    if message.from_user.id in get_admins():
        bot.send_message(message.chat.id, "👑\n" + "\n".join(map(str, get_admins())))


@bot.message_handler(commands=['ban'])
def ban(message):
    if message.from_user.id in get_admins():
        try:
            user_id = int(message.text.split()[1])
            cursor.execute("INSERT INTO banned VALUES (?)", (user_id,))
            conn.commit()
            bot.send_message(message.chat.id, f"🚫 {user_id} забанений")
        except:
            bot.send_message(message.chat.id, "❌ /ban ID")


@bot.message_handler(commands=['unban'])
def unban(message):
    if message.from_user.id in get_admins():
        try:
            user_id = int(message.text.split()[1])
            cursor.execute("DELETE FROM banned WHERE id=?", (user_id,))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ {user_id} розбанений")
        except:
            bot.send_message(message.chat.id, "❌ /unban ID")


@bot.message_handler(content_types=['text','photo','video','document','audio','voice','sticker'])
def handle(message):
    try:
        user = message.from_user

        if user.id in get_banned():
            return

        
        if user.id in get_admins():
            if message.reply_to_message:
                user_id = user_messages.get(message.reply_to_message.message_id)
                if user_id:
                    bot.copy_message(user_id, message.chat.id, message.message_id)

       
        else:
            info = (
                f"👤 {user.first_name}\n"
                f"🆔 {user.id}\n"
                f"🔗 @{user.username if user.username else 'none'}"
            )

            for admin in get_admins():
                try:
                    bot.send_message(admin, info)
                    msg = bot.copy_message(admin, message.chat.id, message.message_id)
                    user_messages[msg.message_id] = user.id
                except:
                    pass

    except Exception as e:
        print("Ошибка:", e)

#анти-краш
while True:
    try:
        print("Бот працює...")
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print("Restart:", e)
        time.sleep(3)
