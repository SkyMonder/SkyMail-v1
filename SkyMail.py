from flask import Flask, request, redirect, session, render_template_string, send_file
import sqlite3, os, smtplib, ssl
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "skymail_secret"

SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---- БАЗА ----
def db():
    return sqlite3.connect("skymail.db", check_same_thread=False)

with db() as con:
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        subject TEXT,
        body TEXT,
        file TEXT
    )""")

# ---- ГЛАВНАЯ ----
@app.route("/")
def index():
    if "user" not in session:
        return redirect("/login")
    return redirect("/inbox")

# ---- РЕГИСТРАЦИЯ ----
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user = request.form["email"]
        password = generate_password_hash(request.form["password"])

        if not user.endswith("@skymail.ru"):
            return "Разрешены только @skymail.ru"

        try:
            with db() as con:
                con.cursor().execute("INSERT INTO users (email,password) VALUES (?,?)", (user, password))
            return redirect("/login")
        except:
            return "Такой пользователь уже существует"

    return render_template_string(TEMPLATE_REGISTER)

# ---- ВХОД ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["email"]
        password = request.form["password"]

        with db() as con:
            c = con.cursor()
            c.execute("SELECT password FROM users WHERE email=?", (user,))
            data = c.fetchone()

        if data and check_password_hash(data[0], password):
            session["user"] = user
            return redirect("/inbox")

        return "Неверный логин или пароль"

    return render_template_string(TEMPLATE_LOGIN)

# ---- ВЫХОД ----
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---- ВХОДЯЩИЕ ----
@app.route("/inbox")
def inbox():
    if "user" not in session:
        return redirect("/login")

    with db() as con:
        c = con.cursor()
        c.execute("SELECT sender,subject,body,file FROM messages WHERE receiver=?", (session["user"],))
        messages = c.fetchall()

    return render_template_string(TEMPLATE_INBOX, messages=messages, user=session["user"])

# ---- ФАЙЛ ----
@app.route("/file/<name>")
def file(name):
    return send_file(os.path.join(UPLOAD_FOLDER, name), as_attachment=True)

# ---- ОТПРАВКА ----
@app.route("/send", methods=["POST"])
def send():
    sender = session["user"]
    receiver = request.form["to"]
    subject = request.form["subject"]
    body = request.form["body"]

    file = request.files.get("file")
    filename = ""

    if file and file.filename:
        filename = file.filename
        file.save(os.path.join(UPLOAD_FOLDER, filename))

    # ВНУТРИ SKYMAIL
    if receiver.endswith("@skymail.ru"):
        with db() as con:
            con.cursor().execute(
                "INSERT INTO messages (sender,receiver,subject,body,file) VALUES (?,?,?,?,?)",
                (sender, receiver, subject, body, filename)
            )

    # ВНЕШНЯЯ ОТПРАВКА
    else:
        msg = EmailMessage()
        msg["From"] = SMTP_USER
        msg["To"] = receiver
        msg["Subject"] = f"[SkyMail] {subject}"

        msg.set_content(f"""
От: {sender}
Кому: {receiver}

{body}
""")

        if filename:
            with open(os.path.join(UPLOAD_FOLDER, filename), "rb") as f:
                msg.add_attachment(f.read(), maintype="application", subtype="octet-stream", filename=filename)

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10, context=context) as smtp:
                smtp.login(SMTP_USER, SMTP_PASS)
                smtp.send_message(msg)
            print("✅ Отправлено через Яндекс")
        except Exception as e:
            print("❌ SMTP ОШИБКА:", e)
            return f"Ошибка SMTP: {e}"

    return redirect("/inbox")

# ---- ДИЗАЙН ----
STYLE = """
<style>
body { background:#0f172a; color:white; font-family:Arial; }
.box { width:380px; margin:70px auto; background:#020617; padding:25px; border-radius:12px; box-shadow:0 0 20px black }
input,textarea { width:100%; padding:10px; margin:5px 0; background:#020617; color:white; border:1px solid #334155; border-radius:6px }
button { width:100%; padding:12px; background:#2563eb; color:white; border:none; border-radius:6px; cursor:pointer }
button:hover { background:#1d4ed8 }
hr { border:1px solid #1e293b }
a { color:#60a5fa }
.msg { background:#020617; padding:10px; border-radius:8px; margin-top:10px }
</style>
"""

TEMPLATE_REGISTER = STYLE + """
<div class="box">
<h2>Регистрация SkyMail</h2>
<form method=post>
<input name=email placeholder="user@skymail.ru" required>
<input type=password name=password placeholder="Пароль" required>
<button>Создать</button>
</form>
<a href="/login">Войти</a>
</div>
"""

TEMPLATE_LOGIN = STYLE + """
<div class="box">
<h2>Вход SkyMail</h2>
<form method=post>
<input name=email required>
<input type=password name=password required>
<button>Войти</button>
</form>
<a href="/register">Регистрация</a>
</div>
"""

TEMPLATE_INBOX = STYLE + """
<div class="box">
<h2>{{ user }}</h2>
<a href="/logout">Выйти</a>

<h3>Отправка</h3>
<form method=post action="/send" enctype=multipart/form-data>
<input name=to placeholder="Кому" required>
<input name=subject placeholder="Тема" required>
<textarea name=body placeholder="Сообщение" required></textarea>
<input type=file name=file>
<button>Отправить</button>
</form>

<h3>Входящие</h3>
{% for m in messages %}
<div class="msg">
<b>От:</b> {{ m[0] }}<br>
<b>Тема:</b> {{ m[1] }}<br>
{{ m[2] }}<br>
{% if m[3] %}
<a href="/file/{{ m[3] }}">Скачать файл</a>
{% endif %}
</div>
{% endfor %}
</div>
"""

# ---- ЗАПУСК ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
