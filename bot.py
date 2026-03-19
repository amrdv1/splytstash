import telebot
import time
import sqlite3
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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


# --- СТАРТ ---
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id in get_banned():
        return
    bot.send_message(
        message.chat.id,
        "Привіт,сюди ви можете надсилати свої демки, меми, питання та пропозиції,які будуть відправлені адміністраторам."
    )


# --- HELP ---
@bot.message_handler(commands=['adminhelp'])
def admin_help(message):
    if message.from_user.id in get_admins():
        bot.send_message(
            message.chat.id,
            "👨‍💻 Команди адміна:\n\n"
            "/admins — список адмінів\n"
            "/ban ID — забанити\n"
            "/unban ID — розбанити\n"
            "/done — завершити заявку (reply)\n"
            "/adminhelp — цей список"
        )


# --- КНОПКА ВЗЯТИ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("take_"))
def take_request(call):
    admin_id = call.from_user.id

    if admin_id not in get_admins():
        return

    msg_id = int(call.data.split("_")[1])

    cursor.execute("SELECT status, admin_name FROM requests WHERE msg_id=?", (msg_id,))
    data = cursor.fetchone()

    if not data:
        return

    status, admin_name = data

    if status == "done":
        bot.answer_callback_query(call.id, "❌ Вже завершено")
        return

    if admin_name:
        bot.answer_callback_query(call.id, f"❌ Вже взяв: {admin_name}")
        return

    admin_name = call.from_user.first_name

    cursor.execute(
        "UPDATE requests SET status='in_progress', admin_name=? WHERE msg_id=?",
        (admin_name, msg_id)
    )
    conn.commit()

    for admin in get_admins():
        try:
            bot.send_message(admin, f"🚧 Заявку взяв: {admin_name}")
        except:
            pass

    bot.answer_callback_query(call.id, "✅ Ти взяв заявку")


# --- DONE ---
@bot.message_handler(commands=['done'])
def done(message):
    if message.from_user.id in get_admins():
        if message.reply_to_message:
            msg_id = message.reply_to_message.message_id

            cursor.execute("SELECT status FROM requests WHERE msg_id=?", (msg_id,))
            data = cursor.fetchone()

            if not data:
                bot.send_message(message.chat.id, "❌ Не знайдено")
                return

            if data[0] == "done":
                bot.send_message(message.chat.id, "⚠️ Вже завершено")
                return

            cursor.execute("UPDATE requests SET status='done' WHERE msg_id=?", (msg_id,))
            conn.commit()

            for admin in get_admins():
                bot.send_message(admin, f"🏁 Заявка {msg_id} завершена")


# --- ОСНОВА ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle(message):
    try:
        user = message.from_user

        if user.id in get_banned():
            return

        # --- АДМІН ---
        if user.id in get_admins():
            if message.reply_to_message:
                msg_id = message.reply_to_message.message_id

                cursor.execute("SELECT user_id, admin_name FROM requests WHERE msg_id=?", (msg_id,))
                data = cursor.fetchone()

                if not data:
                    return

                user_id, admin_name = data

                if admin_name and admin_name != user.first_name:
                    bot.send_message(message.chat.id, f"❌ Вже взяв: {admin_name}")
                    return

                bot.copy_message(user_id, message.chat.id, message.message_id)

        # --- КОРИСТУВАЧ ---
        else:
            info = (
                f"👤 {user.first_name}\n"
                f"🆔 {user.id}\n"
                f"🔗 @{user.username if user.username else 'none'}"
            )

            for admin in get_admins():
                try:
                    bot.send_message(admin, info)

msg = bot.copy_message(
    admin,
    message.chat.id,
    message.message_id
)

# кнопка окремим повідомленням
markup = InlineKeyboardMarkup()
markup.add(InlineKeyboardButton(
    "✅ Взяти в роботу",
    callback_data=f"take_{msg.message_id}"
))

bot.send_message(
    admin,
    "👇 Взяти заявку:",
    reply_markup=markup
)

                    bot.edit_message_reply_markup(
                        chat_id=admin,
                        message_id=msg.message_id,
                        reply_markup=markup
                    )

                    # 3. запис в базу
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
