from flask import Flask, render_template_string, request, redirect, session, url_for
import json
import os

app = Flask(__name__)
app.secret_key = "skymail_secret_key"
DATA_FILE = "skymail_data.json"

# Загрузка данных
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
else:
    data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

# Основной шаблон
layout = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>SkyMail</title>
<style>
body { font-family: Arial, sans-serif; background: #f2f2f2; margin:0; padding:0;}
header { background: #004080; color: white; padding: 10px;}
.container { width: 80%%; margin: 20px auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1);}
input, textarea { width: 100%%; padding: 10px; margin: 5px 0; border-radius: 4px; border: 1px solid #ccc;}
button { padding: 10px 20px; border:none; background: #004080; color:white; border-radius: 4px; cursor:pointer;}
button:hover { background: #0066cc;}
nav a { margin-right: 10px; color:white; text-decoration:none; font-weight:bold;}
table { width: 100%%; border-collapse: collapse;}
th, td { border: 1px solid #ccc; padding: 10px; text-align:left;}
th { background: #f0f0f0;}
</style>
</head>
<body>
<header>
  <h1>SkyMail</h1>
  {% if 'user' in session %}
  <nav>
    <a href="{{ url_for('inbox') }}">Входящие</a>
    <a href="{{ url_for('compose') }}">Написать письмо</a>
    <a href="{{ url_for('logout') }}">Выйти</a>
  </nav>
  {% endif %}
</header>
<div class="container">
{{ content|safe }}
</div>
</body>
</html>
"""

# Главная регистрация
@app.route("/", methods=["GET", "POST"])
def index():
    msg = ""
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if username in data:
            msg = "Пользователь уже существует!"
        else:
            data[username] = {"password": password, "inbox": []}
            save_data()
            msg = f"Почта создана: {username}@skymail.ru"
    content = f"""
    <h2>Регистрация</h2>
    <form method="post">
      <input type="text" name="username" placeholder="Имя пользователя" required>
      <input type="password" name="password" placeholder="Пароль" required>
      <button type="submit">Зарегистрироваться</button>
    </form>
    <p>Уже есть аккаунт? <a href="{url_for('login')}">Войти</a></p>
    <p style="color:red;">{msg}</p>
    """
    return render_template_string(layout, content=content)

# Вход
@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if username in data and data[username]["password"] == password:
            session['user'] = username
            return redirect(url_for('inbox'))
        else:
            msg = "Неверные данные"
    content = f"""
    <h2>Вход</h2>
    <form method="post">
      <input type="text" name="username" placeholder="Имя пользователя" required>
      <input type="password" name="password" placeholder="Пароль" required>
      <button type="submit">Войти</button>
    </form>
    <p>Нет аккаунта? <a href="{url_for('index')}">Зарегистрироваться</a></p>
    <p style="color:red;">{msg}</p>
    """
    return render_template_string(layout, content=content)

# Выход
@app.route("/logout")
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

# Входящие
@app.route("/inbox")
def inbox():
    if 'user' not in session:
        return redirect(url_for('login'))
    inbox_list = data[session['user']]['inbox']
    if inbox_list:
        rows = ""
        for msg in inbox_list:
            rows += f"<tr><td>{msg['from']}@skymail.ru</td><td>{msg['subject']}</td><td>{msg['body']}</td></tr>"
        table = f"<table><tr><th>От кого</th><th>Тема</th><th>Сообщение</th></tr>{rows}</table>"
    else:
        table = "<p>Входящие пусты.</p>"
    content = f"<h2>Входящие</h2>{table}"
    return render_template_string(layout, content=content)

# Написать письмо
@app.route("/compose", methods=["GET", "POST"])
def compose():
    if 'user' not in session:
        return redirect(url_for('login'))
    msg = ""
    if request.method == "POST":
        recipient = request.form['to'].strip()
        subject = request.form['subject'].strip()
        body = request.form['body'].strip()
        if recipient not in data:
            msg = "Пользователь не найден!"
        else:
            data[recipient]["inbox"].append({"from": session['user'], "subject": subject, "body": body})
            save_data()
            msg = "Письмо отправлено!"
    content = f"""
    <h2>Написать письмо</h2>
    <form method="post">
      <input type="text" name="to" placeholder="Кому (только @skymail.ru)" required>
      <input type="text" name="subject" placeholder="Тема" required>
      <textarea name="body" placeholder="Сообщение" rows="6" required></textarea>
      <button type="submit">Отправить</button>
    </form>
    <p style="color:green;">{msg}</p>
    """
    return render_template_string(layout, content=content)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)



