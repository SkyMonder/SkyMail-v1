from flask import Flask, render_template_string, request, redirect, session, url_for, send_from_directory
import json
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "skymail_secret_key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "skymail_data.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Загрузка данных
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Шаблон
layout = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>SkyMail</title>
<style>
body {font-family: Arial; background:#f2f2f2; margin:0}
header {background:#004080; color:white; padding:10px}
.container {width:85%%; margin:20px auto; background:white; padding:20px; border-radius:8px}
input, textarea {width:100%%; padding:10px; margin:6px 0}
button {padding:10px 20px; background:#004080; color:white; border:none; cursor:pointer}
nav a {color:white; margin-right:10px; text-decoration:none}
table {width:100%%; border-collapse:collapse}
th, td {border:1px solid #ccc; padding:8px}
th {background:#eee}
</style>
</head>
<body>
<header>
<h1>SkyMail</h1>
{% if 'user' in session %}
<nav>
<a href="/inbox">Входящие</a>
<a href="/compose">Написать</a>
<a href="/logout">Выйти</a>
</nav>
{% endif %}
</header>
<div class="container">
{{ content|safe }}
</div>
</body>
</html>
"""

# Регистрация
@app.route("/", methods=["GET", "POST"])
def index():
    msg = ""
    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"].strip()
        if u in data:
            msg = "Пользователь существует!"
        else:
            data[u] = {"password": p, "inbox": []}
            save_data()
            msg = f"Почта создана: {u}@skymail.ru"

    content = f"""
    <h2>Регистрация</h2>
    <form method="post">
    <input name="username" placeholder="Логин">
    <input type="password" name="password" placeholder="Пароль">
    <button>Создать</button>
    </form>
    <p><a href="/login">Войти</a></p>
    <p style="color:red">{msg}</p>
    """
    return render_template_string(layout, content=content)

# Вход
@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        if u in data and data[u]["password"] == p:
            session["user"] = u
            return redirect("/inbox")
        else:
            msg = "Неверные данные"

    content = f"""
    <h2>Вход</h2>
    <form method="post">
    <input name="username">
    <input type="password" name="password">
    <button>Войти</button>
    </form>
    <p style="color:red">{msg}</p>
    """
    return render_template_string(layout, content=content)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# Входящие
@app.route("/inbox")
def inbox():
    if "user" not in session:
        return redirect("/login")

    rows = ""
    for m in data[session["user"]]["inbox"]:
        file_link = f'<a href="/file/{m["file"]}">Скачать</a>' if m["file"] else "—"
        rows += f"<tr><td>{m['from']}</td><td>{m['subject']}</td><td>{m['body']}</td><td>{file_link}</td></tr>"

    content = f"""
    <h2>Входящие</h2>
    <table>
    <tr><th>От</th><th>Тема</th><th>Сообщение</th><th>Файл</th></tr>
    {rows}
    </table>
    """
    return render_template_string(layout, content=content)

# Отправка письма + файла
@app.route("/compose", methods=["GET", "POST"])
def compose():
    if "user" not in session:
        return redirect("/login")

    msg = ""
    if request.method == "POST":
        to = request.form["to"].replace("@skymail.ru", "").strip()
        subject = request.form["subject"]
        body = request.form["body"]

        file = request.files.get("file")
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))

        if to not in data:
            msg = "Пользователь не найден!"
        else:
            data[to]["inbox"].append({
                "from": session["user"] + "@skymail.ru",
                "subject": subject,
                "body": body,
                "file": filename
            })
            save_data()
            msg = "Письмо отправлено!"

    content = f"""
    <h2>Новое письмо</h2>
    <form method="post" enctype="multipart/form-data">
    <input name="to" placeholder="Кому">
    <input name="subject" placeholder="Тема">
    <textarea name="body"></textarea>
    <input type="file" name="file">
    <button>Отправить</button>
    </form>
    <p style="color:green">{msg}</p>
    """
    return render_template_string(layout, content=content)

# Скачивание файлов
@app.route("/file/<filename>")
def file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

# Запуск
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
