import os
import json
import uuid
import bcrypt
import requests
from flask import Flask, request, jsonify

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

# --- Flask приложение ---
app = Flask(__name__)

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
    return response.status_code == 200, response.text

# --- Роуты Flask ---
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    users = load_json(USERS_FILE)
    if username in users:
        return jsonify({"error": "Пользователь уже существует"}), 400
    users[username] = {
        "password": hash_password(password),
        "email": f"{username}@skymail.ru",
        "inbox": []
    }
    save_json(USERS_FILE, users)
    return jsonify({"message": f"Аккаунт создан: {username}@skymail.ru"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    users = load_json(USERS_FILE)
    if username not in users or not check_password(password, users[username]["password"]):
        return jsonify({"error": "Неверный логин или пароль"}), 401
    return jsonify({"message": f"Привет, {username}!"}), 200

@app.route("/send_internal", methods=["POST"])
def send_internal():
    data = request.json
    from_user = data.get("from")
    to_user = data.get("to")
    subject = data.get("subject")
    text = data.get("text")
    users = load_json(USERS_FILE)
    if from_user not in users or to_user not in users:
        return jsonify({"error": "Пользователь не найден"}), 404
    users[to_user]["inbox"].append({
        "from": users[from_user]["email"],
        "subject": subject,
        "text": text
    })
    save_json(USERS_FILE, users)
    return jsonify({"message": "Сообщение доставлено во внутренний ящик"}), 200

@app.route("/inbox/<username>", methods=["GET"])
def inbox(username):
    users = load_json(USERS_FILE)
    if username not in users:
        return jsonify({"error": "Пользователь не найден"}), 404
    return jsonify(users[username]["inbox"]), 200

@app.route("/send_external", methods=["POST"])
def send_external_route():
    data = request.json
    sender_sky = data.get("from")
    to_email = data.get("to")
    subject = data.get("subject")
    text = data.get("text")
    success, msg = send_external(to_email, subject, text, sender_sky)
    if success:
        return jsonify({"message": "Письмо успешно отправлено через Mailgun"}), 200
    return jsonify({"error": msg}), 500

@app.route("/request_password_reset", methods=["POST"])
def request_password_reset():
    data = request.json
    username = data.get("username")
    users = load_json(USERS_FILE)
    tokens = load_json(TOKENS_FILE)
    if username not in users:
        return jsonify({"error": "Пользователь не найден"}), 404
    token = str(uuid.uuid4())
    tokens[token] = username
    save_json(TOKENS_FILE, tokens)
    send_external(users[username]["email"], "Сброс пароля",
                  f"Используйте этот токен для сброса: {token}", "SkyMail")
    return jsonify({"message": "Письмо с токеном отправлено на ваш email"}), 200

@app.route("/reset_password", methods=["POST"])
def reset_password():
    data = request.json
    token = data.get("token")
    new_password = data.get("new_password")
    tokens = load_json(TOKENS_FILE)
    if token not in tokens:
        return jsonify({"error": "Неверный токен"}), 400
    username = tokens.pop(token)
    save_json(TOKENS_FILE, tokens)
    users = load_json(USERS_FILE)
    users[username]["password"] = hash_password(new_password)
    save_json(USERS_FILE, users)
    return jsonify({"message": f"Пароль для {username} успешно изменён"}), 200

# --- Запуск сервера ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
