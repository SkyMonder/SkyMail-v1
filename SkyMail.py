# SkyMail - Мини-почтовый сервис в одном файле
# Упрощённая версия Mail.ru/Yandex для обучения и тестов
# Требует: pip install flask flask_session werkzeug email_validator

import os, smtplib, imaplib, email, uuid, datetime
from email.message import EmailMessage
from flask import Flask, request, redirect, url_for, session, render_template_string, send_from_directory
from flask_session import Session
from werkzeug.utils import secure_filename
from email_validator import validate_email, EmailNotValidError

# === Настройки сервера ===
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = set(['txt','pdf','png','jpg','jpeg','gif'])
SMTP_HOST = 'smtp.yandex.ru'  # внешний SMTP для отправки писем
SMTP_PORT = 587
SMTP_USER = 'skymonder@yandex.ru'
SMTP_PASSWORD = 'ВАШ_ПАРОЛЬ_ОТ_YANDEX'

# === Инициализация приложения ===
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# === Хранилище данных в памяти ===
USERS = {}  # email: {password, inbox:[], sent:[], drafts:[], spam:[]}
# Пример структуры письма:
# {id, from, to, subject, body, date, attachments:[filename,...]}

# === Вспомогательные функции ===
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS

def current_user():
    return session.get('user_email')

def save_email(user_email, mail, folder='inbox'):
    USERS[user_email][folder].append(mail)

def send_external_email(to_email, subject, body, attachments=[]):
    msg = EmailMessage()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body)
    for fpath in attachments:
        with open(fpath,'rb') as f:
            data = f.read()
            fname = os.path.basename(fpath)
            msg.add_attachment(data, maintype='application', subtype='octet-stream', filename=fname)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

# === Основной шаблон ===
layout = """
<!DOCTYPE html>
<html>
<head>
    <title>SkyMail</title>
    <style>
        body{font-family:Arial,sans-serif;margin:0;padding:0;background:#f0f0f0;}
        header{background:#4a90e2;color:white;padding:10px;}
        nav a{margin:0 10px;color:white;text-decoration:none;}
        main{padding:20px;}
        .mail-list{list-style:none;padding:0;}
        .mail-list li{background:white;margin:5px 0;padding:10px;border-radius:5px;}
    </style>
</head>
<body>
<header>
    SkyMail | {% if user %}{{ user }} | <a href="{{ url_for('logout') }}">Logout</a>{% else %}<a href="{{ url_for('login') }}">Login</a>{% endif %}
</header>
<main>
{% block content %}{% endblock %}
</main>
</body>
</html>
"""

# === Маршруты ===

@app.route('/')
def index():
    user = current_user()
    if user:
        return redirect(url_for('inbox'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    error=''
    if request.method=='POST':
        email_input = request.form['email'].lower()
        password = request.form['password']
        try:
            v = validate_email(email_input)
            email_input = v.email
        except EmailNotValidError:
            error='Некорректный email'
            email_input=''
        if email_input in USERS:
            error='Email уже зарегистрирован'
        if not error:
            USERS[email_input] = {'password':password,'inbox':[],'sent':[],'drafts':[],'spam':[]}
            session['user_email'] = email_input
            return redirect(url_for('inbox'))
    return render_template_string(layout+"""
{% block content %}
<h2>Регистрация</h2>
<form method="post">
    Email:<br><input type="email" name="email" required><br>
    Пароль:<br><input type="password" name="password" required><br><br>
    <input type="submit" value="Регистрация">
</form>
<p style="color:red;">{{ error }}</p>
{% endblock %}
""", error=error, user=current_user())

@app.route('/login', methods=['GET','POST'])
def login():
    error=''
    if request.method=='POST':
        email_input = request.form['email'].lower()
        password = request.form['password']
        if email_input in USERS and USERS[email_input]['password']==password:
            session['user_email'] = email_input
            return redirect(url_for('inbox'))
        else:
            error='Неверный email или пароль'
    return render_template_string(layout+"""
{% block content %}
<h2>Вход</h2>
<form method="post">
    Email:<br><input type="email" name="email" required><br>
    Пароль:<br><input type="password" name="password" required><br><br>
    <input type="submit" value="Вход">
</form>
<p style="color:red;">{{ error }}</p>
<p>Нет аккаунта? <a href="{{ url_for('register') }}">Регистрация</a></p>
{% endblock %}
""", error=error, user=current_user())

@app.route('/logout')
def logout():
    session.pop('user_email',None)
    return redirect(url_for('login'))

@app.route('/inbox')
def inbox():
    user = current_user()
    if not user: return redirect(url_for('login'))
    mails = USERS[user]['inbox']
    return render_template_string(layout+"""
{% block content %}
<h2>Входящие</h2>
<a href="{{ url_for('compose') }}">Написать письмо</a><br><br>
<ul class="mail-list">
{% for m in mails %}
<li><b>От:</b> {{ m['from'] }} | <b>Тема:</b> <a href="{{ url_for('view_mail', mail_id=m['id'], folder='inbox') }}">{{ m['subject'] }}</a> | {{ m['date'] }}</li>
{% else %}<li>Пусто</li>{% endfor %}
</ul>
{% endblock %}
""", mails=mails, user=user)

@app.route('/sent')
def sent():
    user = current_user()
    if not user: return redirect(url_for('login'))
    mails = USERS[user]['sent']
    return render_template_string(layout+"""
{% block content %}
<h2>Отправленные</h2>
<a href="{{ url_for('compose') }}">Написать письмо</a><br><br>
<ul class="mail-list">
{% for m in mails %}
<li><b>Кому:</b> {{ m['to'] }} | <b>Тема:</b> <a href="{{ url_for('view_mail', mail_id=m['id'], folder='sent') }}">{{ m['subject'] }}</a> | {{ m['date'] }}</li>
{% else %}<li>Пусто</li>{% endfor %}
</ul>
{% endblock %}
""", mails=mails, user=user)

@app.route('/compose', methods=['GET','POST'])
def compose():
    user = current_user()
    if not user: return redirect(url_for('login'))
    error=''
    if request.method=='POST':
        to_email = request.form['to'].lower()
        subject = request.form['subject']
        body = request.form['body']
        attachments=[]
        # сохранение вложений
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                fpath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(fpath)
                attachments.append(fpath)
        mail = {'id':str(uuid.uuid4()), 'from':user, 'to':to_email, 'subject':subject, 'body':body,
                'date':datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'attachments':[os.path.basename(f) for f in attachments]}
        # если пользователь внутри системы
        if to_email in USERS:
            save_email(to_email, mail, folder='inbox')
        else:
            try:
                send_external_email(to_email, subject, body, attachments)
            except Exception as e:
                error=f"Ошибка отправки внешнему пользователю: {e}"
        save_email(user, mail, folder='sent')
        if not error:
            return redirect(url_for('sent'))
    return render_template_string(layout+"""
{% block content %}
<h2>Написать письмо</h2>
<form method="post" enctype="multipart/form-data">
    Кому:<br><input type="email" name="to" required><br>
    Тема:<br><input type="text" name="subject"><br>
    Текст:<br><textarea name="body" rows="5" cols="40"></textarea><br>
    Вложение:<br><input type="file" name="file"><br><br>
    <input type="submit" value="Отправить">
</form>
<p style="color:red;">{{ error }}</p>
{% endblock %}
""", error=error, user=user)

@app.route('/mail/<folder>/<mail_id>')
def view_mail(folder, mail_id):
    user = current_user()
    if not user: return redirect(url_for('login'))
    mail_list = USERS[user].get(folder,[])
    mail = next((m for m in mail_list if m['id']==mail_id), None)
    if not mail: return "Письмо не найдено"
    return render_template_string(layout+"""
{% block content %}
<h2>{{ mail.subject }}</h2>
<p><b>От:</b> {{ mail.from }}</p>
<p><b>Кому:</b> {{ mail.to }}</p>
<p><b>Дата:</b> {{ mail.date }}</p>
<p>{{ mail.body }}</p>
{% if mail.attachments %}
<h4>Вложения:</h4>
<ul>{% for f in mail.attachments %}
<li><a href="{{ url_for('download_file', filename=f) }}">{{ f }}</a></li>
{% endfor %}</ul>
{% endif %}
<a href="{{ url_for('inbox') }}">Назад</a>
{% endblock %}
""", mail=mail, user=user)

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# === Запуск сервера ===
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)
