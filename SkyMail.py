from flask import Flask, request, redirect, url_for, session, render_template_string
from email_validator import validate_email, EmailNotValidError
import smtplib, imaplib, email

app = Flask(__name__)
app.secret_key = "supersecretkey"

# База пользователей (email -> password)
users = {}

def current_user():
    return session.get("user")

layout = """
<!DOCTYPE html>
<html>
<head>
    <title>SkyMail</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        header h1 { display: inline; }
        nav a { margin: 0 10px; text-decoration: none; }
        .content { margin-top: 20px; }
        .error { color: red; }
        .success { color: green; }
        input, textarea { margin-bottom: 10px; width: 300px; }
    </style>
</head>
<body>
<header>
    <h1>SkyMail</h1>
    <nav>
        {% if user %}
            <a href="{{ url_for('inbox') }}">Inbox</a>
            <a href="{{ url_for('compose') }}">Compose</a>
            <a href="{{ url_for('logout') }}">Logout</a>
        {% else %}
            <a href="{{ url_for('login') }}">Login</a>
            <a href="{{ url_for('register') }}">Register</a>
        {% endif %}
    </nav>
</header>
<hr>
<div class="content">
{% block content %}{% endblock %}
</div>
</body>
</html>
"""

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
        confirm = request.form.get("confirm")
        if password != confirm:
            error = "Passwords do not match"
        else:
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
    return render_template_string(layout + """
{% block content %}
<h2>Register</h2>
<p class="error">{{ error }}</p>
<form method="post">
    <label>Email:</label><input type="email" name="email" required><br>
    <label>Password:</label><input type="password" name="password" required><br>
    <label>Confirm Password:</label><input type="password" name="confirm" required><br>
    <input type="submit" value="Register">
</form>
{% endblock %}
""", error=error, user=current_user())

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
<p class="error">{{ error }}</p>
<form method="post">
    <label>Email:</label><input type="email" name="email" required><br>
    <label>Password:</label><input type="password" name="password" required><br>
    <input type="submit" value="Login">
</form>
{% endblock %}
""", error=error, user=current_user())

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
            smtp = smtplib.SMTP_SSL("smtp.yandex.com", 465)
            smtp.login(current_user(), users[current_user()])
            message = f"Subject: {subject}\n\n{body}"
            smtp.sendmail(current_user(), to_addr, message)
            smtp.quit()
            success = "Email sent successfully!"
        except Exception as e:
            error = str(e)
    return render_template_string(layout + """
{% block content %}
<h2>Compose Email</h2>
<p class="success">{{ success }}</p>
<p class="error">{{ error }}</p>
<form method="post">
    <label>To:</label><input type="email" name="to" required><br>
    <label>Subject:</label><input type="text" name="subject" required><br>
    <label>Body:</label><br>
    <textarea name="body" rows="5" cols="50" required></textarea><br>
    <input type="submit" value="Send">
</form>
{% endblock %}
""", error=error, success=success, user=current_user())

@app.route("/inbox")
def inbox():
    if not current_user():
        return redirect(url_for("login"))
    emails_list = []
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.com")
        imap.login(current_user(), users[current_user()])
        imap.select("INBOX")
        status, data = imap.search(None, "ALL")
        for num in data[0].split():
            status, msg_data = imap.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            emails_list.append({
                "from": msg["From"],
                "subject": msg["Subject"]
            })
        imap.logout()
    except Exception as e:
        emails_list.append({"from":"Error", "subject": str(e)})
    return render_template_string(layout + """
{% block content %}
<h2>Inbox</h2>
<ul>
    {% for email in emails %}
        <li><strong>From:</strong> {{ email.from }} | <strong>Subject:</strong> {{ email.subject }}</li>
    {% endfor %}
</ul>
{% endblock %}
""", emails=emails_list, user=current_user())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
