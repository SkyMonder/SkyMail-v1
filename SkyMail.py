from flask import Flask, render_template_string, request, redirect, session, url_for, flash
import hashlib
import json
import os
import imaplib
import email
import smtplib
from email.mime.text import MIMEText
import threading
import time

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # На проде поменять на случайный

FILENAME = "skymail_data.json"

# ---------- Внешний почтовый мост ----------
EXTERNAL_EMAIL = "skymonder@yandex.ru"
EXTERNAL_PASSWORD = "ПарольПриложения"

# ---------- Работа с данными ----------
def load_data():
    if os.path.exists(FILENAME):
        with open(FILENAME, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(FILENAME, "w") as f:
        json.dump(data, f, indent=4)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------- Главная страница ----------
@app.route("/")
def index():
    return redirect(url_for("login"))

# ---------- Регистрация ----------
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        data = load_data()
        username = request.form["username"].strip()
        email_addr = f"{username}@skymail.ru"
        if email_addr in data:
            flash("Такой пользователь уже существует!")
            return redirect(url_for("register"))
        password = request.form["password"]
        secret_question = request.form["secret_question"]
        secret_answer = request.form["secret_answer"]
        data[email_addr] = {
            "password": hash_password(password),
            "secret_question": secret_question,
            "secret_answer": hash_password(secret_answer),
            "inbox": []
        }
        save_data(data)
        flash(f"Аккаунт {email_addr} успешно создан!")
        return redirect(url_for("login"))
    return render_template_string(REGISTER_TEMPLATE)

# ---------- Вход ----------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        data = load_data()
        email_addr = request.form["email"]
        password = request.form["password"]
        if email_addr in data and data[email_addr]["password"] == hash_password(password):
            session["email"] = email_addr
            flash(f"Добро пожаловать, {email_addr}!")
            return redirect(url_for("inbox"))
        flash("Неверный email или пароль!")
        return redirect(url_for("login"))
    return render_template_string(LOGIN_TEMPLATE)

# ---------- Восстановление пароля ----------
@app.route("/recover", methods=["GET","POST"])
def recover():
    data = load_data()
    if request.method == "POST":
        email_addr = request.form["email"]
        if email_addr not in data:
            flash("Такого пользователя не существует!")
            return redirect(url_for("recover"))
        if "answer" in request.form:
            answer = request.form["answer"]
            if data[email_addr]["secret_answer"] == hash_password(answer):
                new_password = request.form["new_password"]
                data[email_addr]["password"] = hash_password(new_password)
                save_data(data)
                flash("Пароль успешно изменён!")
                return redirect(url_for("login"))
            else:
                flash("Неверный ответ на секретный вопрос!")
                return redirect(url_for("recover"))
        question = data[email_addr]["secret_question"]
        return render_template_string(RECOVER_QUESTION_TEMPLATE, email=email_addr, question=question)
    return render_template_string(RECOVER_TEMPLATE)

# ---------- Выход ----------
@app.route("/logout")
def logout():
    session.pop("email", None)
    flash("Вы вышли из системы.")
    return redirect(url_for("login"))

# ---------- Входящие ----------
@app.route("/inbox")
def inbox():
    if "email" not in session:
        return redirect(url_for("login"))
    data = load_data()
    inbox = data[session["email"]]["inbox"]
    return render_template_string(INBOX_TEMPLATE, inbox=inbox, email=session["email"])

# ---------- Отправка письма ----------
@app.route("/send", methods=["GET","POST"])
def send():
    if "email" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        data = load_data()
        recipient = request.form["recipient"].strip()
        subject = request.form["subject"]
        body = request.form["body"]
        status_msg = ""
        # Отправка внутреннему пользователю SkyMail
        if recipient in data:
            message = {"from": session["email"], "subject": subject, "body": body}
            data[recipient]["inbox"].append(message)
            status_msg += "Внутренний получатель: успешно. "
        # Отправка внешнему email через Yandex SMTP
        try:
            send_external_email(recipient, subject, body)
            status_msg += "Внешний получатель: успешно."
        except Exception as e:
            status_msg += f"Ошибка отправки внешнему получателю: {e}"
        save_data(data)
        flash(status_msg)
        return redirect(url_for("inbox"))
    return render_template_string(SEND_TEMPLATE)

# ---------- Функция получения писем с внешнего ящика ----------
def fetch_external_emails():
    data = load_data()
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.ru")
        imap.login(EXTERNAL_EMAIL, EXTERNAL_PASSWORD)
        imap.select("INBOX")
        status, messages = imap.search(None, 'ALL')  # берём все письма
        for num in messages[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            recipient = msg.get("To")
            if recipient not in data:
                continue

            sender = msg.get("From")
            subject = msg.get("Subject", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()

            message = {"from": sender, "subject": subject, "body": body}
            data[recipient]["inbox"].append(message)
        save_data(data)
        imap.logout()
    except Exception as e:
        print("Ошибка при получении писем:", e)

# ---------- Функция отправки через внешний SMTP ----------
def send_external_email(to, subject, body):
    smtp = smtplib.SMTP_SSL("smtp.yandex.ru", 465)
    smtp.login(EXTERNAL_EMAIL, EXTERNAL_PASSWORD)
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EXTERNAL_EMAIL
    msg["To"] = to
    smtp.sendmail(EXTERNAL_EMAIL, to, msg.as_string())
    smtp.quit()

# ---------- Фоновый поток проверки внешней почты ----------
def email_fetcher_thread():
    while True:
        fetch_external_emails()
        time.sleep(60)  # каждые 60 секунд

threading.Thread(target=email_fetcher_thread, daemon=True).start()

# ==================== Шаблоны ====================

REGISTER_TEMPLATE = """<html>... (тот же код, как выше, со всеми формами) ...</html>"""
LOGIN_TEMPLATE = """<html>... </html>"""
RECOVER_TEMPLATE = """<html>...</html>"""
RECOVER_QUESTION_TEMPLATE = """<html>...</html>"""
INBOX_TEMPLATE = """<html>...</html>"""
SEND_TEMPLATE = """<html>...</html>"""

# ---------- Запуск ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
