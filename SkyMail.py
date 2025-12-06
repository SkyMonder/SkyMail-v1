import os
import json
import uuid
import bcrypt
import requests
from flask import Flask, request, jsonify, render_template_string, redirect, url_for

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

# --- HTML шаблоны ---
INDEX_HTML = """
<!doctype html>
<title>SkyMail</title>
<h1>Добро пожаловать в SkyMail</h1>
<a href="/register_form">Регистрация</a> | 
<a href="/login_form">Вход</a>
"""

REGISTER_HTML = """
<!doctype html>
<title>Регистрация</title>
<h1>Регистрация</h1>
<form method="post" action="/register_form">
  Имя пользователя: <input type="text" name="username"><br>
  Пароль: <input type="password" name="password"><br>
  <input type="submit" value="Зарегистрироваться">
</form>
<a href="/">Главная</a>
"""

LOGIN_HTML = """
<!doctype html>
<title>Вход</title>
<h1>Вход</h1>
<form method="post" action="/login_form">
  Имя пользователя: <input type="text" name="username"><br>
  Пароль: <input type="password" name="password"><br>
  <input type="submit" value="Войти">
</form>
<a href="/">Главная</a>
"""

DASHBOARD_HTML = """
<!doctype html>
<title>SkyMail Dashboard</title>
<h1>Привет, {{username}}</h1>
<h2>Входящие:</h2>
<ul>
{% for mail in inbox %}
<li><b>От:</b> {{mail['from']}} | <b>Тема:</b> {{mail['subject']}}<br>{{mail['text']}}</li>
{% else %}
<li>Входящие пусты</li>
{% endfor %}
</ul>

<h2>Отправить внутреннее письмо:</h2>
<form method="post" action="/send_internal_form">
<input type="hidden" name="from_user" value="{{username}}">
Кому (username): <input type="text" name="to_user"><br>
Тема: <input type="text" name="subject"><br>
Сообщение: <br><textarea name="text"></textarea><br>
<input type="submit" value="Отправить">
</form>

<h2>Отправить внешнее письмо:</h2>
<form method="post" action="/send_external_form">
<input type="hidden" name="from_user" value="{{username}}">
Кому (email): <input type="text" name="to_email"><br>
Тема: <input type="text" name="subject"><br>
Сообщение: <br><textarea name="text"></textarea><br>
<input type="submit" value="Отправить">
</form>

<a href="/">Выйти</a>
"""

# --- Flask маршруты ---
@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/register_form", methods=["GET", "POST"])
def register_form():
    if request.method == "GET":
        return render_template_string(REGISTER_HTML)
    username = request.form["username"]
    password = request.form["password"]
    users = load_json(USERS_FILE)
    if username in users:
        return "Пользователь уже существует"
    users[username] = {
        "password": hash_password(password),
        "email": f"{username}@skymail.ru",
        "inbox": []
    }
    save_json(USERS_FILE, users)
    return redirect(url_for("login_form"))

@app.route("/login_form", methods=["GET", "POST"])
def login_form():
    if request.method == "GET":
        return render_template_string(LOGIN_HTML)
    username = request.form["username"]
    password = request.form["password"]
    users = load_json(USERS_FILE)
    if username not in users or not check_password(password, users[username]["password"]):
        return "Неверный логин или пароль"
    inbox = users[username]["inbox"]
    return render_template_string(DASHBOARD_HTML, username=username, inbox=inbox)

@app.route("/send_internal_form", methods=["POST"])
def send_internal_form():
    from_user = request.form["from_user"]
    to_user = request.form["to_user"]
    subject = request.form["subject"]
    text = request.form["text"]
    users = load_json(USERS_FILE)
    if from_user not in users or to_user not in users:
        return "Пользователь не найден"
    users[to_user]["inbox"].append({
        "from": users[from_user]["email"],
        "subject": subject,
        "text": text
    })
    save_json(USERS_FILE, users)
    return redirect(url_for("login_form") + f"?username={from_user}")

@app.route("/send_external_form", methods=["POST"])
def send_external_form():
    from_user = request.form["from_user"]
    to_email = request.form["to_email"]
    subject = request.form["subject"]
    text = request.form["text"]
    success, msg = send_external(to_email, subject, text, f"{from_user}@skymail.ru")
    if success:
        return f"Письмо успешно отправлено на {to_email}"
    else:
        return f"Ошибка при отправке: {msg}"

# --- API маршруты (JSON) ---
@app.route("/api/register", methods=["POST"])
def api_register():
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
    return jsonify({"message": "Аккаунт создан"}), 201

@app.route("/api/send_external", methods=["POST"])
def api_send_external():
    data = request.json
    sender_sky = data.get("from")
    to_email = data.get("to")
    subject = data.get("subject")
    text = data.get("text")
    success, msg = send_external(to_email, subject, text, sender_sky)
    if success:
        return jsonify({"message": "Письмо успешно отправлено"}), 200
    return jsonify({"error": msg}), 500

# --- Запуск ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
