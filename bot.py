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
            "/addadmin ID\n"
            "/removeadmin ID\n"
            "/admins\n"
            "/ban ID\n"
            "/unban ID\n"
        )


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


# --- КНОПКА ВЗЯТИ ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("take_"))
def take_request(call):
    if call.from_user.id not in get_admins():
        return

    msg_id = int(call.data.split("_")[1])

    cursor.execute("SELECT status, admin_name FROM requests WHERE msg_id=?", (msg_id,))
    data = cursor.fetchone()

    if not data:
        return

    status, admin_name = data

    if admin_name:
        bot.answer_callback_query(call.id, f"❌ Вже взяв: {admin_name}")
        return

    name = call.from_user.first_name

    cursor.execute(
        "UPDATE requests SET status='in_progress', admin_name=? WHERE msg_id=?",
        (name, msg_id)
    )
    conn.commit()

    for admin in get_admins():
        bot.send_message(admin, f"🚧 В роботі: {name}")

    # додаємо кнопку завершення
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(
        "🏁 Завершити",
        callback_data=f"done_{msg_id}"
    ))

    bot.send_message(call.from_user.id, "Ти взяв заявку", reply_markup=markup)
    bot.answer_callback_query(call.id)


# --- КНОПКА DONE ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("done_"))
def done_request(call):
    if call.from_user.id not in get_admins():
        return

    msg_id = int(call.data.split("_")[1])

    cursor.execute("SELECT admin_name FROM requests WHERE msg_id=?", (msg_id,))
    data = cursor.fetchone()

    if not data:
        return

    admin_name = data[0]

    if admin_name != call.from_user.first_name:
        bot.answer_callback_query(call.id, "❌ Не твоя заявка")
        return

    cursor.execute("UPDATE requests SET status='done' WHERE msg_id=?", (msg_id,))
    conn.commit()

    for admin in get_admins():
        bot.send_message(admin, f"🏁 Завершено: {admin_name}")

    bot.answer_callback_query(call.id, "✅ Завершено")


# --- ОСНОВА ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle(message):
    try:
        user = message.from_user

        if user.id in get_banned():
            return

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

        else:
            info = (
                f"👤 {user.first_name}\n"
                f"🆔 {user.id}\n"
                f"🔗 @{user.username if user.username else 'none'}"
            )

            for admin in get_admins():
                bot.send_message(admin, info)

                msg = bot.copy_message(admin, message.chat.id, message.message_id)

                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton(
                    "✅ Взяти в роботу",
                    callback_data=f"take_{msg.message_id}"
                ))

                bot.send_message(admin, "👇 Взяти заявку:", reply_markup=markup)

                cursor.execute(
                    "INSERT INTO requests VALUES (?, ?, ?, ?)",
                    (msg.message_id, user.id, "new", None)
                )
                conn.commit()

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
