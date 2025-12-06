from flask import Flask, render_template_string, request, redirect, session, url_for
import hashlib
import json
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # На проде поменяй на случайный

FILENAME = "skymail_data.json"

# Работа с данными
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

# Главная
@app.route("/")
def index():
    if "email" in session:
        return redirect(url_for("inbox"))
    return render_template_string("""
    <h1>SkyMail</h1>
    <a href="/register">Регистрация</a> | <a href="/login">Вход</a> | <a href="/recover">Восстановление пароля</a>
    """)

# Регистрация
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = load_data()
        username = request.form["username"].strip()
        email = f"{username}@skymail.ru"
        if email in data:
            return "Такой пользователь уже существует!"
        password = request.form["password"]
        secret_question = request.form["secret_question"]
        secret_answer = request.form["secret_answer"]
        data[email] = {
            "password": hash_password(password),
            "secret_question": secret_question,
            "secret_answer": hash_password(secret_answer),
            "inbox": []
        }
        save_data(data)
        return redirect(url_for("login"))
    return render_template_string("""
    <h1>Регистрация</h1>
    <form method="post">
        Имя пользователя: <input name="username"><br>
        Пароль: <input type="password" name="password"><br>
        Секретный вопрос: <input name="secret_question"><br>
        Ответ на секретный вопрос: <input name="secret_answer"><br>
        <input type="submit" value="Зарегистрироваться">
    </form>
    """)

# Вход
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = load_data()
        email = request.form["email"]
        password = request.form["password"]
        if email in data and data[email]["password"] == hash_password(password):
            session["email"] = email
            return redirect(url_for("inbox"))
        return "Неверный email или пароль!"
    return render_template_string("""
    <h1>Вход</h1>
    <form method="post">
        Email: <input name="email"><br>
        Пароль: <input type="password" name="password"><br>
        <input type="submit" value="Войти">
    </form>
    """)

# Восстановление пароля
@app.route("/recover", methods=["GET", "POST"])
def recover():
    if request.method == "POST":
        data = load_data()
        email = request.form["email"]
        if email not in data:
            return "Такого пользователя не существует."
        if "answer" in request.form:
            answer = request.form["answer"]
            if data[email]["secret_answer"] == hash_password(answer):
                new_password = request.form["new_password"]
                data[email]["password"] = hash_password(new_password)
                save_data(data)
                return redirect(url_for("login"))
            return "Неверный ответ!"
        question = data[email]["secret_question"]
        return render_template_string("""
        <h1>Ответьте на секретный вопрос</h1>
        <form method="post">
            <input type="hidden" name="email" value="{{email}}">
            Вопрос: {{question}}<br>
            Ответ: <input name="answer"><br>
            Новый пароль: <input name="new_password"><br>
            <input type="submit" value="Сменить пароль">
        </form>
        """, email=email, question=question)
    return render_template_string("""
    <h1>Восстановление пароля</h1>
    <form method="post">
        Email: <input name="email"><br>
        <input type="submit" value="Далее">
    </form>
    """)

# Входящие
@app.route("/inbox")
def inbox():
    if "email" not in session:
        return redirect(url_for("login"))
    data = load_data()
    inbox = data[session["email"]]["inbox"]
    return render_template_string("""
    <h1>Входящие для {{email}}</h1>
    <a href="/send">Отправить письмо</a> | <a href="/logout">Выйти</a>
    <ul>
    {% for msg in inbox %}
        <li><b>От:</b> {{msg.from}} | <b>Тема:</b> {{msg.subject}}<br>{{msg.body}}</li>
    {% else %}
        <li>Входящие пусты.</li>
    {% endfor %}
    </ul>
    """, email=session["email"], inbox=inbox)

# Отправка письма
@app.route("/send", methods=["GET", "POST"])
def send():
    if "email" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        data = load_data()
        recipient = request.form["recipient"]
        if recipient not in data:
            return "Пользователь не найден."
        message = {
            "from": session["email"],
            "subject": request.form["subject"],
            "body": request.form["body"]
        }
        data[recipient]["inbox"].append(message)
        save_data(data)
        return redirect(url_for("inbox"))
    return render_template_string("""
    <h1>Отправка письма</h1>
    <form method="post">
        Кому: <input name="recipient"><br>
        Тема: <input name="subject"><br>
        Сообщение: <textarea name="body"></textarea><br>
        <input type="submit" value="Отправить">
    </form>
    """)

@app.route("/logout")
def logout():
    session.pop("email", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
