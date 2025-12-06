# SkyMail.py
from flask import Flask, render_template_string, request, redirect, url_for, session
import imaplib
import smtplib
from email.message import EmailMessage
import email
from email_validator import validate_email, EmailNotValidError

app = Flask(__name__)
app.secret_key = "supersecretkey"

# -------------------------
# HTML шаблон
# -------------------------
layout = """
<!DOCTYPE html>
<html>
<head>
    <title>SkyMail</title>
</head>
<body>
    <h1>SkyMail</h1>
    {% if user %}
        <p>Logged in as {{ user }}</p>
        <p><a href="{{ url_for('logout') }}">Logout</a></p>
        <p><a href="{{ url_for('inbox') }}">Inbox</a> | <a href="{{ url_for('compose') }}">Compose</a></p>
    {% else %}
        <p><a href="{{ url_for('login') }}">Login</a> | <a href="{{ url_for('register') }}">Register</a></p>
    {% endif %}
    <hr>
    {% block content %}{% endblock %}
</body>
</html>
"""

# -------------------------
# Пользователи (локально)
# -------------------------
users = {}  # {email: password} -- для примера, хранить в базе лучше

def current_user():
    return session.get("user")

# -------------------------
# Регистрация
# -------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        email_addr = request.form.get("email")
        password = request.form.get("password")
        try:
            validate_email(email_addr)
        except EmailNotValidError:
            error = "Invalid email address"
            return render_template_string(layout + """
            {% block content %}
            <h2>Register</h2>
            <p style="color:red">{{ error }}</p>
            <form method="post">
                Email: <input type="text" name="email"><br>
                Password: <input type="password" name="password"><br>
                <input type="submit" value="Register">
            </form>
            {% endblock %}
            """, error=error)
        if email_addr in users:
            error = "Email already registered"
        else:
            users[email_addr] = password
            session["user"] = email_addr
            return redirect(url_for("inbox"))

    return render_template_string(layout + """
    {% block content %}
    <h2>Register</h2>
    <p style="color:red">{{ error }}</p>
    <form method="post">
        Email: <input type="text" name="email"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Register">
    </form>
    {% endblock %}
    """, error=error)

# -------------------------
# Логин
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        email_addr = request.form.get("email")
        password = request.form.get("password")
        if users.get(email_addr) == password:
            session["user"] = email_addr
            return redirect(url_for("inbox"))
        else:
            error = "Invalid credentials"
    return render_template_string(layout + """
    {% block content %}
    <h2>Login</h2>
    <p style="color:red">{{ error }}</p>
    <form method="post">
        Email: <input type="text" name="email"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    {% endblock %}
    """, error=error)

# -------------------------
# Logout
# -------------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# -------------------------
# Inbox (IMAP)
# -------------------------
@app.route("/inbox")
def inbox():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    password = users[user]
    messages = []

    try:
        imap_server = "imap.yandex.com"
        mail = imaplib.IMAP4_SSL(imap_server)
        mail.login(user, password)
        mail.select("inbox")
        status, data = mail.search(None, "ALL")
        mail_ids = data[0].split()
        latest_ids = mail_ids[-10:]  # последние 10 писем
        for i in reversed(latest_ids):
            status, msg_data = mail.fetch(i, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    messages.append({
                        "from": msg["From"],
                        "subject": msg["Subject"],
                        "body": msg.get_payload(decode=True).decode(errors="ignore")[:200]
                    })
        mail.logout()
    except Exception as e:
        messages.append({"from": "", "subject": "Error", "body": str(e)})

    return render_template_string(layout + """
    {% block content %}
    <h2>Inbox</h2>
    {% for msg in messages %}
        <b>From:</b> {{ msg.from }} <br>
        <b>Subject:</b> {{ msg.subject }} <br>
        <pre>{{ msg.body }}</pre>
        <hr>
    {% endfor %}
    {% endblock %}
    """, messages=messages, user=user)

# -------------------------
# Compose / Send Email (SMTP)
# -------------------------
@app.route("/compose", methods=["GET", "POST"])
def compose():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    
    error = ""
    if request.method == "POST":
        to_addr = request.form.get("to")
        subject = request.form.get("subject")
        body = request.form.get("body")
        try:
            validate_email(to_addr)
            password = users[user]
            msg = EmailMessage()
            msg["From"] = user
            msg["To"] = to_addr
            msg["Subject"] = subject
            msg.set_content(body)

            smtp_server = "smtp.yandex.com"
            with smtplib.SMTP_SSL(smtp_server, 465) as server:
                server.login(user, password)
                server.send_message(msg)
            return redirect(url_for("inbox"))
        except EmailNotValidError:
            error = "Invalid recipient email"
        except Exception as e:
            error = str(e)

    return render_template_string(layout + """
    {% block content %}
    <h2>Compose Email</h2>
    <p style="color:red">{{ error }}</p>
    <form method="post">
        To: <input type="text" name="to"><br>
        Subject: <input type="text" name="subject"><br>
        Body:<br>
        <textarea name="body" rows="10" cols="50"></textarea><br>
        <input type="submit" value="Send">
    </form>
    {% endblock %}
    """, error=error, user=user)

# -------------------------
# Главная страница
# -------------------------
@app.route("/")
def index():
    if current_user():
        return redirect(url_for("inbox"))
    return redirect(url_for("login"))

# -------------------------
# Запуск
# -------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
