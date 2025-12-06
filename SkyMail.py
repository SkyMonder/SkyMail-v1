from flask import Flask, request, redirect, url_for, session, render_template_string
from email_validator import validate_email, EmailNotValidError
import smtplib
import imaplib
import email

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Простая база пользователей (email -> password)
users = {}

# Базовый шаблон без блоков
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
        <p><a href="{{ url_for('logout') }}">Logout</a> | <a href="{{ url_for('inbox') }}">Inbox</a> | <a href="{{ url_for('compose') }}">Compose</a></p>
    {% else %}
        <p><a href="{{ url_for('login') }}">Login</a> | <a href="{{ url_for('register') }}">Register</a></p>
    {% endif %}
    <hr>
    {{ content|safe }}
</body>
</html>
"""

# Получение текущего пользователя
def current_user():
    return session.get("user")

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("inbox"))
    return redirect(url_for("login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""
    if request.method == "POST":
        email_addr = request.form.get("email")
        password = request.form.get("password")
        try:
            validate_email(email_addr)
        except EmailNotValidError as e:
            error = str(e)
        else:
            if email_addr in users:
                error = "User already exists"
            else:
                users[email_addr] = password
                session["user"] = email_addr
                return redirect(url_for("inbox"))

    form = f"""
    <h2>Register</h2>
    <p style="color:red">{error}</p>
    <form method="post">
        Email: <input type="text" name="email"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Register">
    </form>
    """
    return render_template_string(layout, content=form, user=current_user())

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

    form = f"""
    <h2>Login</h2>
    <p style="color:red">{error}</p>
    <form method="post">
        Email: <input type="text" name="email"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    """
    return render_template_string(layout, content=form, user=current_user())

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/compose", methods=["GET", "POST"])
def compose():
    if not current_user():
        return redirect(url_for("login"))

    error = ""
    success = ""
    if request.method == "POST":
        to_addr = request.form.get("to")
        subject = request.form.get("subject")
        body = request.form.get("body")
        try:
            validate_email(to_addr)
            # Настройки для Yandex
            smtp = smtplib.SMTP_SSL("smtp.yandex.com", 465)
            smtp.login(current_user(), users[current_user()])
            message = f"Subject: {subject}\n\n{body}"
            smtp.sendmail(current_user(), to_addr, message)
            smtp.quit()
            success = "Email sent successfully!"
        except Exception as e:
            error = str(e)

    form = f"""
    <h2>Compose</h2>
    <p style="color:green">{success}</p>
    <p style="color:red">{error}</p>
    <form method="post">
        To: <input type="text" name="to"><br>
        Subject: <input type="text" name="subject"><br>
        Body:<br><textarea name="body" rows="5" cols="40"></textarea><br>
        <input type="submit" value="Send">
    </form>
    """
    return render_template_string(layout, content=form, user=current_user())

@app.route("/inbox")
def inbox():
    if not current_user():
        return redirect(url_for("login"))

    emails = []
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.com")
        imap.login(current_user(), users[current_user()])
        imap.select("INBOX")
        status, data = imap.search(None, "ALL")
        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            emails.append(f"From: {msg['From']} | Subject: {msg['Subject']}")
        imap.logout()
    except Exception as e:
        emails.append(f"Error fetching emails: {str(e)}")

    inbox_html = "<h2>Inbox</h2>" + "<br>".join(emails)
    return render_template_string(layout, content=inbox_html, user=current_user())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
