# SkyMail PRO FULL — внутренние и внешние письма, вложения
from flask import Flask, render_template_string, request, redirect, session, url_for, send_from_directory
import json, os, smtplib, imaplib, email, threading, time
from email.message import EmailMessage
from email.header import decode_header
from werkzeug.utils import secure_filename
from markupsafe import escape

app = Flask(__name__)
app.secret_key = os.environ.get("SKYMAIL_SECRET", "skymail_secret_key")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "skymail_data.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# ------------------ ДАННЫЕ ------------------
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
else:
    data = {}

# глобальный счетчик id сообщений
if "_next_id" not in data:
    data["_next_id"] = 1

def next_id():
    i = data["_next_id"]
    data["_next_id"] += 1
    return i

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------ ШАБЛОН HTML ------------------
layout = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>SkyMail PRO FULL</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:Arial,sans-serif;background:#f5f7fb;margin:0}
header{background:#0b4f9b;color:#fff;padding:12px 18px;display:flex;justify-content:space-between;align-items:center}
header h1{margin:0;font-size:20px}
nav a{color:#fff;margin-left:12px;text-decoration:none;font-weight:600}
.wrap{max-width:1000px;margin:20px auto;padding:16px}
.card{background:#fff;border-radius:10px;padding:16px;box-shadow:0 6px 18px rgba(15,23,42,0.06)}
table{width:100%;border-collapse:collapse}
th,td{padding:10px;border-bottom:1px solid #eee;text-align:left}
tr.unread{background:#eef6ff}
.small{font-size:13px;color:#666}
.link{color:#0b63c6;text-decoration:none}
.file-link{font-size:13px;color:#0b63c6}
input, textarea{width:100%;padding:8px;border:1px solid #ddd;border-radius:8px;margin-top:8px}
input[type=file]{padding:6px}
.btn{background:#0b63c6;color:#fff;padding:8px 12px;border-radius:8px;border:none;cursor:pointer}
.danger{color:#b00020}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
</style>
</head>
<body>
<header>
<h1>SkyMail PRO FULL</h1>
<div>
{% if 'user' in session %}
  <span class="small">{{ session['user'] }}@skymail.ru</span>
  <nav style="display:inline">
    <a href="{{ url_for('inbox') }}">Входящие</a>
    <a href="{{ url_for('sent') }}">Отправленные</a>
    <a href="{{ url_for('compose') }}">Написать</a>
    <a href="{{ url_for('logout') }}">Выйти</a>
  </nav>
{% else %}
  <a href="{{ url_for('index') }}" class="link">Регистрация</a> |
  <a href="{{ url_for('login') }}" class="link">Войти</a>
{% endif %}
</div>
</header>

<div class="wrap">
  <div class="card">
    {{ content|safe }}
  </div>
</div>

</body>
</html>
"""

# ------------------ МАРШРУТЫ ------------------

# Главная / Регистрация
@app.route("/", methods=["GET","POST"])
def index():
    msg = ""
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        if not username or not password:
            msg = "Укажите логин и пароль."
        elif username in data:
            msg = "Пользователь уже существует."
        else:
            data[username] = {"password": password, "inbox": [], "sent": [], "external": {}}
            save_data()
            msg = f"Аккаунт создан: {escape(username)}@skymail.ru"
    content = f"""
    <h2>Регистрация</h2>
    <form method="post">
      <input name="username" placeholder="Логин (без @skymail.ru)" required>
      <input type="password" name="password" placeholder="Пароль" required>
      <div style="margin-top:10px"><button class="btn">Создать аккаунт</button></div>
    </form>
    <p class="small">Уже есть аккаунт? <a href="{url_for('login')}" class="link">Войти</a></p>
    <p class="danger">{escape(msg)}</p>
    """
    return render_template_string(layout, content=content)

# Вход
@app.route("/login", methods=["GET","POST"])
def login():
    msg = ""
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        if username in data and data[username]["password"] == password:
            session["user"] = username
            return redirect(url_for("inbox"))
        else:
            msg = "Неверный логин или пароль."
    content = f"""
    <h2>Вход</h2>
    <form method="post">
      <input name="username" placeholder="Логин" required>
      <input type="password" name="password" placeholder="Пароль" required>
      <div style="margin-top:10px"><button class="btn">Войти</button></div>
    </form>
    <p class="danger">{escape(msg)}</p>
    """
    return render_template_string(layout, content=content)

# Выход
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# Входящие
@app.route("/inbox")
def inbox():
    if "user" not in session:
        return redirect(url_for("login"))
    user = session["user"]
    inbox = data[user].get("inbox", [])
    rows = ""
    for m in inbox:
        subj = escape(m.get("subject",""))
        frm = escape(m.get("from",""))
        body_sn = escape(m.get("body",""))[:120].replace("\n"," ")
        file_cell = f'<a class="file-link" href="{url_for("file", filename=escape(m.get("file")))}">скачать</a>' if m.get("file") else "—"
        cls = "unread" if m.get("unread", True) else ""
        rows += f'<tr class="{cls}"><td><a href="{url_for("view_message", mailbox="inbox", msg_id=m["id"])}" class="link">{subj or "(без темы)"}</a></td><td class="small">{frm}</td><td>{body_sn}</td><td>{file_cell}</td></tr>'
    table = "<table><tr><th>Тема</th><th>От</th><th>Фрагмент</th><th>Вложение</th></tr>"+rows+"</table>" if inbox else "<p>Входящие пусты.</p>"
    content = f"<div class='topbar'><h2>Входящие</h2></div>{table}"
    return render_template_string(layout, content=content)

# Отправленные
@app.route("/sent")
def sent():
    if "user" not in session:
        return redirect(url_for("login"))
    user = session["user"]
    sent_list = data[user].get("sent", [])
    rows = ""
    for m in sent_list:
        subj = escape(m.get("subject",""))
        to = escape(m.get("to",""))
        body_sn = escape(m.get("body",""))[:120].replace("\n"," ")
        file_cell = f'<a class="file-link" href="{url_for("file", filename=escape(m.get("file")))}">скачать</a>' if m.get("file") else "—"
        rows += f'<tr><td><a href="{url_for("view_message", mailbox="sent", msg_id=m["id"])}" class="link">{subj or "(без темы)"}</a></td><td class="small">{to}</td><td>{body_sn}</td><td>{file_cell}</td></tr>'
    table = "<table><tr><th>Тема</th><th>Кому</th><th>Фрагмент</th><th>Вложение</th></tr>"+rows+"</table>" if sent_list else "<p>Отправленные пусты.</p>"
    content = f"<div class='topbar'><h2>Отправленные</h2></div>{table}"
    return render_template_string(layout, content=content)

# Композировать письмо (внутренние и внешние)
@app.route("/compose", methods=["GET","POST"])
def compose():
    if "user" not in session:
        return redirect(url_for("login"))
    msg = ""
    if request.method == "POST":
        to_raw = request.form.get("to","").strip()
        to_user = to_raw.replace("@skymail.ru","").strip()
        subject = request.form.get("subject","").strip()
        body = request.form.get("body","").strip()
        # Файл
        file = request.files.get("file")
        filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(save_path):
                filename = f"{base}_{counter}{ext}"
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                counter +=1
            file.save(save_path)

        # Внутренние письма SkyMail
        if to_user in data:
            mid = next_id()
            inbox_msg = {"id": mid,"from":session['user']+"@skymail.ru","subject":subject,"body":body,"file":filename,"unread":True}
            data[to_user].setdefault("inbox",[]).append(inbox_msg)
            sent_msg = {"id": mid,"to":to_user,"subject":subject,"body":body,"file":filename}
            data[session['user']].setdefault("sent",[]).append(sent_msg)
            save_data()
            msg="Письмо отправлено внутри SkyMail!"
        else:
            # Внешняя отправка через SMTP
            try:
                smtp_server = "smtp.mail.ru"
                smtp_port = 465
                smtp_user = os.environ.get("SMTP_USER") # логин SkyMail пользователя для внешних SMTP
                smtp_pass = os.environ.get("SMTP_PASS") # пароль приложения
                if not smtp_user or not smtp_pass:
                    raise Exception("SMTP_USER или SMTP_PASS не заданы")
                email_msg = EmailMessage()
                email_msg['From'] = smtp_user
                email_msg['To'] = to_raw
                email_msg['Subject'] = subject
                email_msg.set_content(body)
                if filename:
                    with open(os.path.join(UPLOAD_FOLDER, filename),'rb') as f:
                        email_msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=filename)
                with smtplib.SMTP_SSL(smtp_server,smtp_port) as smtp:
                    smtp.login(smtp_user,smtp_pass)
                    smtp.send_message(email_msg)
                msg="Письмо отправлено внешне!"
            except Exception as e:
                msg=f"Ошибка отправки внешнего письма: {str(e)}"

    content = f"""
    <h2>Написать письмо</h2>
    <form method="post" enctype="multipart/form-data">
      <input name="to" placeholder="Кому (логин или email)"/>
      <input name="subject" placeholder="Тема"/>
      <textarea name="body" rows="6" placeholder="Текст письма"></textarea>
      <input type="file" name="file"/>
      <div style="margin-top:10px"><button class="btn">Отправить</button></div>
    </form>
    <p class="small">{escape(msg)}</p>
    """
    return render_template_string(layout, content=content)

# Просмотр письма
@app.route("/message/<mailbox>/<int:msg_id>")
def view_message(mailbox,msg_id):
    if "user" not in session:
        return redirect(url_for("login"))
    user = session["user"]
    found=None
    if mailbox=="inbox":
        for m in data[user].get("inbox",[]):
            if int(m.get("id"))==msg_id:
                found=m
                if m.get("unread",True):
                    m["unread"]=False
                    save_data()
                break
    elif mailbox=="sent":
        for m in data[user].get("sent",[]):
            if int(m.get("id"))==msg_id:
                found=m
                break
    if not found:
        return "Письмо не найдено",404

    if mailbox=="inbox":
        subj = escape(found.get("subject",""))
        sender = escape(found.get("from",""))
        body = escape(found.get("body","")).replace("\n","<br>")
        file_block = f'<p>Вложение: <a class="file-link" href="{url_for("file", filename=escape(found.get("file")))}">скачать</a></p>' if found.get("file") else ""
        content = f"<h2>{subj or '(без темы)'}</h2><p class='small'>От: {sender}</p><div style='margin-top:12px'>{body}</div>{file_block}<p style='margin-top:12px'><a href='{url_for('inbox')}' class='link'>Назад во входящие</a></p>"
    else:
        subj = escape(found.get("subject",""))
        to = escape(found.get("to",""))
        body = escape(found.get("body","")).replace("\n","<br>")
        file_block = f'<p>Вложение: <a class="file-link" href="{url_for("file", filename=escape(found.get("file")))}">скачать</a></p>' if found.get("file") else ""
        content = f"<h2>{subj or '(без темы)'}</h2><p class='small'>Кому: {to}@skymail.ru</p><div style='margin-top:12px'>{body}</div>{file_block}<p style='margin-top:12px'><a href='{url_for('sent')}' class='link'>Назад в отправленные</a></p>"
    return render_template_string(layout, content=content)

# Скачивание файла
@app.route("/file/<path:filename>")
def file(filename):
    safe = secure_filename(filename)
    path = os.path.join(UPLOAD_FOLDER,safe)
    if not os.path.exists(path):
        return "Файл не найден",404
    return send_from_directory(UPLOAD_FOLDER,safe,as_attachment=True)

# ------------------ Фоновый таск для IMAP ------------------
def fetch_external_mail(user, imap_user, imap_pass):
    try:
        imap = imaplib.IMAP4_SSL("imap.mail.ru")
        imap.login(imap_user, imap_pass)
        imap.select("INBOX")
        status, messages = imap.search(None,"UNSEEN")
        for num in messages[0].split():
            res, msg_data = imap.fetch(num,"(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])
            sender = msg.get("From")
            subject = decode_header(msg.get("Subject"))[0][0]
            if isinstance(subject, bytes): subject = subject.decode()
            body=""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type()=="text/plain":
                        body+=part.get_payload(decode=True).decode()
            else:
                body=msg.get_payload(decode=True).decode()
            mid = next_id()
            inbox_msg={"id":mid,"from":sender,"subject":subject,"body":body,"file":None,"unread":True}
            data[user].setdefault("inbox",[]).append(inbox_msg)
        save_data()
        imap.logout()
    except Exception as e:
        print(f"Ошибка IMAP: {e}")

def imap_worker():
    while True:
        for user,info in data.items():
            ext = info.get("external",{})
            if ext.get("imap_user") and ext.get("imap_pass"):
                fetch_external_mail(user, ext["imap_user"], ext["imap_pass"])
        time.sleep(300) # каждые 5 минут

# Запуск IMAP воркера в фоне
threading.Thread(target=imap_worker, daemon=True).start()

# ------------------ Запуск ------------------
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)
