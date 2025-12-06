from flask import Flask, request, redirect, url_for, flash, session, send_from_directory, render_template_string
import os, json, hashlib, re, smtplib, threading
from werkzeug.utils import secure_filename
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "skymail_data.json"
FILES_DIR = "files"
ALLOWED_EXTENSIONS = {"txt","pdf","png","jpg","jpeg","gif"}
os.makedirs(FILES_DIR, exist_ok=True)

# ================== Данные ==================
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE,"w") as f:
        json.dump({"users":{},"messages":[]},f)

def load_data():
    with open(DATA_FILE,"r") as f:
        return json.load(f)
def save_data(data):
    with open(DATA_FILE,"w") as f:
        json.dump(data,f,indent=4)
def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()
def allowed_file(filename):
    return "." in filename and filename.rsplit(".",1)[1].lower() in ALLOWED_EXTENSIONS

# ================== SMTP ==================
SMTP_SERVER = "smtp.yandex.com"  # или smtp.mail.ru
SMTP_PORT = 465
SMTP_USER = "skymonder@yandex.ru"  # ваш email
SMTP_PASS = "xdbattimavtxfggf"     # пароль приложения Gmail

def send_external_email(to_email, subject, body, attachments=[]):
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)

        for fpath in attachments:
            with open(fpath, "rb") as f:
                data = f.read()
                fname = os.path.basename(fpath)
                msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=fname)

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print(f"[SMTP] Письмо отправлено на {to_email}")
        return True
    except Exception as e:
        print(f"[SMTP] Ошибка при отправке: {e}")
        return False

def send_email_background(to_email, subject, body, attachments):
    threading.Thread(target=send_external_email, args=(to_email, subject, body, attachments), daemon=True).start()

# ================== Шаблоны с дизайном ==================
base_css = """
<style>
body{font-family:Arial,sans-serif; background:#f5f5f5; padding:20px;}
.container{max-width:700px;margin:auto;background:white;padding:20px;border-radius:10px;box-shadow:0 0 10px rgba(0,0,0,0.1);}
h2{color:#333;text-align:center;}
input,textarea{width:100%;padding:8px;margin:5px 0;border:1px solid #ccc;border-radius:5px;}
input[type=submit]{background:#4CAF50;color:white;border:none;cursor:pointer;}
input[type=submit]:hover{background:#45a049;}
a{color:#4CAF50;text-decoration:none;}
a:hover{text-decoration:underline;}
.flash{padding:10px;border-radius:5px;margin-bottom:10px;}
.flash.success{background:#d4edda;color:#155724;}
.flash.error{background:#f8d7da;color:#721c24;}
hr{border:0;border-top:1px solid #eee;}
</style>
"""

def render_with_css(html):
    return base_css + f"<div class='container'>{html}</div>"

login_html = """
<h2>SkyMail - Вход</h2>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
    <div class="flash {{category}}">{{ message }}</div>
  {% endfor %}
{% endwith %}
<form method="post">
Email: <input type="text" name="email"><br>
Пароль: <input type="password" name="password"><br>
<input type="submit" value="Войти">
</form>
<p><a href="{{ url_for('register') }}">Регистрация</a> | <a href="{{ url_for('recover') }}">Восстановление пароля</a></p>
"""

register_html = """
<h2>SkyMail - Регистрация</h2>
<form method="post">
Логин (без @skymail.ru): <input type="text" name="username"><br>
Пароль: <input type="password" name="password"><br>
Секретный вопрос (для восстановления): <input type="text" name="secret"><br>
<input type="submit" value="Зарегистрироваться">
</form>
<p><a href="{{ url_for('login') }}">Вход</a></p>
"""

recover_html = """
<h2>Восстановление пароля</h2>
<form method="post">
Email: <input type="text" name="email"><br>
Секретный ответ: <input type="text" name="secret"><br>
Новый пароль: <input type="password" name="new_password"><br>
<input type="submit" value="Сбросить пароль">
</form>
<p><a href="{{ url_for('login') }}">Вход</a></p>
"""

inbox_html = """
<h2>SkyMail - Входящие ({{ user }})</h2>
<p><a href="{{ url_for('send') }}">Написать сообщение</a> | <a href="{{ url_for('logout') }}">Выход</a></p>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category,message in messages %}
    <div class="flash {{category}}">{{ message }}</div>
  {% endfor %}
{% endwith %}
{% for msg in messages_list %}
<hr>
<p><b>{{ loop.index }}. От:</b> {{msg['from']}} | <b>Тема:</b> {{msg['subject']}}</p>
<p>{{msg['body']}}</p>
{% if msg.get('files') %}
<p>Файлы: 
{% for f in msg['files'] %}
<a href="{{ url_for('uploaded_file', filename=f) }}">{{ f.split('/')[-1] }}</a>
{% endfor %}
</p>
{% endif %}
{% endfor %}
"""

send_html = """
<h2>Написать сообщение</h2>
<form method="post" enctype="multipart/form-data">
Получатель: <input type="text" name="recipient"><br>
Тема: <input type="text" name="subject"><br>
Сообщение:<br><textarea name="body" rows="5"></textarea><br>
Прикрепить файлы: <input type="file" name="files" multiple><br>
<input type="submit" value="Отправить">
</form>
<p><a href="{{ url_for('inbox') }}">Назад в входящие</a></p>
"""

# ================== Маршруты ==================
@app.route("/", methods=["GET","POST"])
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        data = load_data()
        if email in data["users"] and data["users"][email]["password"]==hash_password(password):
            session["user"]=email
            return redirect(url_for("inbox"))
        flash("Неверный логин или пароль!","error")
    return render_with_css(render_template_string(login_html))

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        secret = request.form["secret"].strip()
        email = f"{username}@skymail.ru"
        data = load_data()
        if email in data["users"]:
            flash("Пользователь уже существует!","error")
            return redirect(url_for("register"))
        data["users"][email]={"password":hash_password(password),"secret":secret}
        save_data(data)
        flash("Аккаунт создан! Войдите в систему.","success")
        return redirect(url_for("login"))
    return render_with_css(render_template_string(register_html))

@app.route("/recover", methods=["GET","POST"])
def recover():
    if request.method=="POST":
        email = request.form["email"].strip()
        answer = request.form["secret"].strip()
        new_password = request.form["new_password"].strip()
        data = load_data()
        if email not in data["users"]:
            flash("Пользователь не найден!","error")
        elif data["users"][email]["secret"]!=answer:
            flash("Неверный ответ!","error")
        else:
            data["users"][email]["password"]=hash_password(new_password)
            save_data(data)
            flash("Пароль изменён!","success")
            return redirect(url_for("login"))
    return render_with_css(render_template_string(recover_html))

@app.route("/send", methods=["GET","POST"])
def send():
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method=="POST":
        sender = session["user"]
        recipient = request.form["recipient"].strip()
        subject = request.form["subject"].strip()
        body = request.form["body"].strip()
        files_list=[]
        uploaded_files=request.files.getlist("files")
        for file in uploaded_files:
            if file and allowed_file(file.filename):
                filename=secure_filename(f"{sender.replace('@','_')}_{file.filename}")
                path = os.path.join(FILES_DIR,filename)
                file.save(path)
                files_list.append(path)
        data=load_data()
        if recipient.endswith("@skymail.ru") and recipient in data["users"]:
            data["messages"].append({"from":sender,"to":recipient,"subject":subject,"body":body,"files":files_list})
            flash("Сообщение отправлено внутреннему пользователю!","success")
        else:
            # Отправка внешнему пользователю через SMTP в фоне
            send_email_background(recipient, subject, body, files_list)
            flash(f"Сообщение отправляется на {recipient} через SMTP!","success")
        save_data(data)
        return redirect(url_for("inbox"))
    return render_with_css(render_template_string(send_html))

@app.route("/inbox")
def inbox():
    if "user" not in session:
        return redirect(url_for("login"))
    data=load_data()
    user=session["user"]
    messages_list=[m for m in data["messages"] if m["to"]==user]
    return render_with_css(render_template_string(inbox_html,messages_list=messages_list,user=user))

@app.route("/files/<filename>")
def uploaded_file(filename):
    return send_from_directory(FILES_DIR,os.path.basename(filename))

@app.route("/logout")
def logout():
    session.pop("user",None)
    flash("Вы вышли из системы.","success")
    return redirect(url_for("login"))

# ================== Запуск ==================
if __name__=="__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)



