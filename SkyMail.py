import json
import bcrypt
import uuid
import os
import requests

# --- Mailgun настройки ---
MAILGUN_API_KEY = "ff202a3964dde38788c732fff98c4a3d-235e4bb2-6a352b7b"
MAILGUN_DOMAIN = "sandbox8ea8e4589e764a13ae5c03789d105bca.mailgun.org"
MAILGUN_FROM = f"SkyMail <skymonder@{MAILGUN_DOMAIN}>"

# --- Файлы хранения данных ---
USERS_FILE = "users.json"
TOKENS_FILE = "tokens.json"

# --- Инициализация файлов ---
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(TOKENS_FILE):
    with open(TOKENS_FILE, "w") as f:
        json.dump({}, f)

# --- Вспомогательные функции ---
def load_json(file):
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# --- Регистрация пользователя ---
def register(username, password):
    users = load_json(USERS_FILE)
    if username in users:
        print("Пользователь уже существует.")
        return
    hashed = hash_password(password)
    users[username] = {
        "password": hashed,
        "email": f"{username}@skymail.ru",
        "inbox": []
    }
    save_json(USERS_FILE, users)
    print(f"Аккаунт создан: {username}@skymail.ru")

# --- Аутентификация ---
def login(username, password):
    users = load_json(USERS_FILE)
    if username not in users:
        print("Пользователь не найден.")
        return False
    if not check_password(password, users[username]["password"]):
        print("Неверный пароль.")
        return False
    print(f"Привет, {username}!")
    return True

# --- Внутренняя почта ---
def send_internal(from_user, to_user, subject, text):
    users = load_json(USERS_FILE)
    if from_user not in users or to_user not in users:
        print("Пользователь не найден.")
        return
    users[to_user]["inbox"].append({
        "from": users[from_user]["email"],
        "subject": subject,
        "text": text
    })
    save_json(USERS_FILE, users)
    print("Сообщение доставлено во внутренний ящик.")

def inbox(username):
    users = load_json(USERS_FILE)
    if username not in users:
        print("Пользователь не найден.")
        return
    mails = users[username]["inbox"]
    if not mails:
        print("Входящие пусты.")
        return
    for i, mail in enumerate(mails, 1):
        print(f"{i}. От: {mail['from']}, Тема: {mail['subject']}\n{mail['text']}\n")

# --- Внешняя почта через Mailgun ---
def send_external(to_email, subject, text, sender_sky):
    full_text = f"{text}\n\n---\nОтправлено с помощью SkyMail от: {sender_sky}"
    response = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data={
            "from": MAILGUN_FROM,
            "to": to_email,
            "subject": subject,
            "text": full_text
        }
    )
    if response.status_code == 200:
        print("Письмо успешно отправлено через Mailgun!")
    else:
        print("Ошибка при отправке:", response.text)

# --- Восстановление пароля ---
def request_password_reset(username):
    users = load_json(USERS_FILE)
    tokens = load_json(TOKENS_FILE)
    if username not in users:
        print("Пользователь не найден.")
        return
    token = str(uuid.uuid4())
    tokens[token] = username
    save_json(TOKENS_FILE, tokens)
    send_external(users[username]["email"], "Сброс пароля",
                  f"Используйте этот токен для сброса: {token}", "SkyMail")
    print("Письмо с токеном отправлено на ваш email.")

def reset_password(token, new_password):
    tokens = load_json(TOKENS_FILE)
    if token not in tokens:
        print("Неверный токен.")
        return
    username = tokens.pop(token)
    save_json(TOKENS_FILE, tokens)
    users = load_json(USERS_FILE)
    users[username]["password"] = hash_password(new_password)
    save_json(USERS_FILE, users)
    print(f"Пароль для {username} успешно изменён.")

# --- Пример использования ---
if __name__ == "__main__":
    # Регистрируем пользователей
    register("alice", "password123")
    register("bob", "securepass")

    # Отправляем внутреннее сообщение
    send_internal("alice", "bob", "Привет", "Это тестовое сообщение внутри SkyMail!")

    # Просмотр входящих
    inbox("bob")

    # Отправляем внешнее письмо через Mailgun
    # send_external("example@gmail.com", "Тема письма", "Текст письма", "alice@skymail.ru")

    # Восстановление пароля (пример)
    # request_password_reset("bob")
    # reset_password("PASTE_YOUR_TOKEN_HERE", "newpassword")
