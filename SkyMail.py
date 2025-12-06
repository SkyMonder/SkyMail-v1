import os
import json
import imaplib
import email
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, session
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from flask_session import Session

# --- Настройка Flask ---
app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATA_FILE = "data.json"
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def next_id():
    return str(max([int(i) for u in data.values() for i in u.get("inbox", [])]+[0])+1)

# --- Настройка Yandex ---
YANDEX_EMAIL = "skymonder@yandex.ru"
YANDEX_PASSWORD = "ВАШ_ПАРОЛЬ_ПРИЛОЖЕНИЯ"

# --- Функция забора внешней почты через Yandex IMAP ---
def fetch_external_mail():
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.com")
        imap.login(YANDEX_EMAIL, YANDEX_PASSWORD)
        imap.select("INBOX")

        status, messages = imap.search(None, "UNSEEN")
        for num in messages[0].split():
            res, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            sender = msg.get("From")
            subject = msg.get("Subject", "")
            body = ""
            attachments = []

            if msg.is_multipart():
                for part in msg.walk():
                    content_disposition = part.get("Content-Disposition")
                    if part.get_content_type() == "text/plain" and not content_disposition:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif content_disposition and "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            filepath = os.path.join(UPLOAD_FOLDER, filename)
                            with open(filepath, "wb") as f:
                                f.write(part.get_payload(decode=True))
                            attachments.append(filename)
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

            # --- Распределение по пользователям SkyMail ---
            if subject.lower().startswith("to:"):
                target_user = subject.split(":", 1)[1].strip()
                if target_user in data:
                    mid = next_id()
                    data[target_user].setdefault("inbox", []).append({
                        "id": mid,
                        "from": sender,
                        "subject": subject,
                        "body": body,
                        "attachments": attachments,
                        "unread": True
                    })
        save_data()
        imap.logout()
    except Exception as e:
        print(f"IMAP bridge error: {e}")

# --- Функция отправки внешних писем через Yandex SMTP ---
def send_external_email(sender, to_email, subject, body, attachments=None):
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    if attachments:
        for file in attachments:
            filepath = os.path.join(UPLOAD_FOLDER, file)
            part = MIMEBase('application', 'octet-stream')
            with open(filepath, 'rb') as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={file}')
            msg.attach(part)

    try:
        server = smtplib.SMTP_SSL('smtp.yandex.com', 465)
        server.login(YANDEX_EMAIL, YANDEX_PASSWORD)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        print(f"Письмо отправлено на {to_email}")
        return True
    except Exception as e:
        print(f"Ошибка при отправке: {e}")
        return False

# --- HTML layout ---
layout = """
<!doctype html>
<title>SkyMail</title>
<h1>SkyMail</h1>
<nav>
  {% if session.get('user') %}
    <a href="{{ url_for('index') }}">Входящие</a> |
    <a href="{{ url_for('compose') }}">Написать письмо</a> |
    <a href="{{ url_for('logout') }}">Выйти</a>
  {% endif %}
</nav>
<hr>
{% block content %}{% endblock %}
"""

# --- Маршрут логина ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        if username not in data:
            return "Пользователь не найден!"
        session['user'] = username
        return redirect(url_for("index"))
    return render_template_string(layout + """
{% block content %}
<h2>Вход в SkyMail</h2>
<form method="post">
Введите имя пользователя: <input name="username">
<input type="submit" value="Войти">
</form>
{% endblock %}
""")

# --- Входящие ---
@app.route("/", methods=["GET"])
def index():
    if 'user' not in session:
        return redirect(url_for("login"))
    fetch_external_mail()
    username = session['user']
    inbox = data[username].get("inbox", [])
    return render_template_string(layout + """
{% block content %}
<h2>Входящие для {{username}}</h2>
<ul>
{% for mail in inbox %}
<li>
<strong>От:</strong> {{mail['from']}} |
<strong>Тема:</strong> {{mail['subject']}} |
{% if mail['attachments'] %}
<strong>Вложения:</strong> 
{% for file in mail['attachments'] %}
<a href="{{ url_for('download_file', filename=file) }}">{{file}}</a>
{% endfor %}
{% endif %}
<p>{{mail['body']}}</p>
</li>
{% endfor %}
</ul>
{% endblock %}
""", username=username, inbox=inbox)

# --- Написать письмо ---
@app.route("/compose", methods=["GET", "POST"])
def compose():
    if 'user' not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        sender = session['user']
        recipient = request.form.get("recipient")
        subject = request.form.get("subject")
        body = request.form.get("body")
        file = request.files.get("file")
        attachments = []

        if file:
            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)
            attachments.append(file.filename)

        if "@" in recipient:  # внешний email
            send_external_email(sender, recipient, subject, body, attachments)
        else:  # внутренний пользователь SkyMail
            if recipient not in data:
                return "Пользователь не найден!"
            mid = next_id()
            data[recipient].setdefault("inbox", []).append({
                "id": mid,
                "from": sender,
                "subject": subject,
                "body": body,
                "attachments": attachments,
                "unread": True
            })
            save_data()

        return redirect(url_for("index"))

    return render_template_string(layout + """
{% block content %}
<h2>Написать письмо</h2>
<form method="post" enctype="multipart/form-data">
Кому: <input type="text" name="recipient"><br>
Тема: <input type="text" name="subject"><br>
Текст: <br><textarea name="body"></textarea><br>
Вложение: <input type="file" name="file"><br>
<input type="submit" value="Отправить">
</form>
{% endblock %}
""")

# --- Скачивание вложений ---
@app.route("/uploads/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# --- Выход ---
@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect(url_for("login"))

# --- Регистрация тестовых пользователей ---
data.setdefault("user1", {"inbox":[]})
data.setdefault("user2", {"inbox":[]})
save_data()

# --- Запуск ---
if __name__ == "__main__":
    app.run(debug=True)
