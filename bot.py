import telebot
import time
import sqlite3
import os

TOKEN = os.getenv("TOKEN")

if not TOKEN:
    raise Exception("Bot token is not defined")

SUPER_ADMIN = 1669340183
bot = telebot.TeleBot(TOKEN)

# база
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS admins (id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS banned (id INTEGER)")

# нова таблиця заявок
cursor.execute("""
CREATE TABLE IF NOT EXISTS requests (
    msg_id INTEGER,
    user_id INTEGER,
    status TEXT,
    admin_name TEXT
)
""")

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
    bot.send_message(message.chat.id,
                     "Привіт,сюди ви можете надсилати свої демки, меми, питання та пропозиції, які будуть відправлені адміністраторам.")


# --- АДМІНИ ---
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


# --- БАН ---
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


# --- ЗАВЕРШЕННЯ ЗАЯВКИ ---
@bot.message_handler(commands=['done'])
def done(message):
    if message.from_user.id in get_admins():
        if message.reply_to_message:
            msg_id = message.reply_to_message.message_id

            cursor.execute("SELECT status FROM requests WHERE msg_id=?", (msg_id,))
            data = cursor.fetchone()

            if not data:
                bot.send_message(message.chat.id, "❌ Не знайдено заявку")
                return

            if data[0] == "done":
                bot.send_message(message.chat.id, "⚠️ Вже завершено")
                return

            cursor.execute("UPDATE requests SET status='done' WHERE msg_id=?", (msg_id,))
            conn.commit()

            for admin in get_admins():
                try:
                    bot.send_message(admin, f"🏁 Заявка {msg_id} завершена")
                except:
                    pass


# --- ОСНОВНА ЛОГІКА ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle(message):
    try:
        user = message.from_user

        if user.id in get_banned():
            return

        # --- АДМІН ВІДПОВІДАЄ ---
        if user.id in get_admins():
            if message.reply_to_message:
                msg_id = message.reply_to_message.message_id

                cursor.execute("SELECT user_id, status, admin_name FROM requests WHERE msg_id=?", (msg_id,))
                data = cursor.fetchone()

                if not data:
                    return

                user_id, status, admin_name = data

                if status == "done":
                    bot.send_message(message.chat.id, "❌ Вже завершено")
                    return

                if admin_name and admin_name != message.from_user.first_name:
                    bot.send_message(message.chat.id, f"❌ Вже взяв: {admin_name}")
                    return

                # якщо ще ніхто не взяв
                if not admin_name:
                    admin_name = message.from_user.first_name
                    cursor.execute(
                        "UPDATE requests SET admin_name=?, status='in_progress' WHERE msg_id=?",
                        (admin_name, msg_id)
                    )
                    conn.commit()

                    for admin in get_admins():
                        bot.send_message(admin, f"🚧 В роботі: {admin_name}")

                # відправка користувачу
                bot.copy_message(user_id, message.chat.id, message.message_id)

        # --- КОРИСТУВАЧ ПИШЕ ---
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

                    # зберігаємо заявку
                    cursor.execute(
                        "INSERT INTO requests VALUES (?, ?, ?, ?)",
                        (msg.message_id, user.id, "new", None)
                    )
                    conn.commit()

                except:
                    pass

    except Exception as e:
        print("Ошибка:", e)


# анти-краш
while True:
    try:
        print("Бот працює...")
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print("Restart:", e)
        time.sleep(3)
