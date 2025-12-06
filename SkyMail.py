from flask import Flask, request, redirect, url_for, flash, session, send_from_directory, render_template_string
import os, json, hashlib, shutil, re
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

DATA_FILE = "skymail_data.json"
FILES_DIR = "files"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif"}
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

# ================== HTML-шаблоны ==================
login_html = """
<h2>SkyMail - Вход</h2>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
    <p style="color:{% if category=='error' %}red{% else %}green{% endif %}">{{ message }}</p>
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
<p><a href="{{ url_for('send') }}">Написать сообщение</a> | <a href="{{ url_for('process_bridge') }}">Обработать мост</a> | <a href="{{ url_for('logout') }}">Выход</a></p>
{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category,message in messages %}
    <p style="color:{% if category=='error' %}red{% else %}green{% endif %}">{{ message }}</p>
  {% endfor %}
{% endwith %}
{% for i,msg in enumerate(messages_list,1) %}
<hr>
<p><b>{{i}}. От:</b> {{msg['from']}} | <b>Тема:</b> {{msg['subject']}}</p>
<p>{{msg['body']}}</p>
{% if msg.get('files') %}
<p>Файлы: 
{% for f in msg['files'] %}
<a href="{{ url_for('uploaded_file', filename=f) }}">{{ f }}</a>
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
Сообщение:<br><textarea name="body" rows="5" cols="50"></textarea><br>
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
    return render_template_string(login_html)

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
    return render_template_string(register_html)

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
    return render_template_string(recover_html)

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
                file.save(os.path.join(FILES_DIR,filename))
                files_list.append(filename)
        data=load_data()
        if recipient.endswith("@skymail.ru") and recipient in data["users"]:
            data["messages"].append({"from":sender,"to":recipient,"subject":subject,"body":body,"files":files_list})
            flash("Сообщение отправлено внутреннему пользователю!","success")
        else:
            bridge_email="skymonder@yandex.ru"
            bridge_message=f"Отправитель:{sender}\nКому:{recipient}\nТема:{subject}\n\n{body}"
            data["messages"].append({"from":sender,"to":bridge_email,"subject":f"[Внешняя почта] Кому: {recipient} | {subject}","body":bridge_message,"files":files_list})
            flash(f"Сообщение отправлено через мост для {recipient}!","success")
        save_data(data)
        return redirect(url_for("inbox"))
    return render_template_string(send_html)

@app.route("/inbox")
def inbox():
    if "user" not in session:
        return redirect(url_for("login"))
    data=load_data()
    user=session["user"]
    messages_list=[m for m in data["messages"] if m["to"]==user]
    return render_template_string(inbox_html,messages_list=messages_list,user=user)

@app.route("/process_bridge")
def process_bridge():
    if "user" not in session:
        return redirect(url_for("login"))
    data=load_data()
    new_messages=[]
    for msg in data["messages"]:
        if msg["to"]=="skymonder@yandex.ru" and "[Внешняя почта]" in msg["subject"]:
            match=re.search(r"Кому: (\S+@skymail\.ru)",msg["subject"])
            if match:
                recipient=match.group(1)
                if recipient in data["users"]:
                    data["messages"].append({"from":msg["from"],"to":recipient,"subject":msg["subject"].replace(f"Кому: {recipient} | ",""),"body":msg["body"],"files":msg.get("files",[])})
                    flash(f"Письмо для {recipient} добавлено во входящие.","success")
                else:
                    flash(f"SkyMail адрес {recipient} не найден, письмо пропущено.","error")
            else:
                flash("В теме письма не найден SkyMail адрес.","error")
            new_messages.append(msg)
    for m in new_messages:
        data["messages"].remove(m)
    save_data(data)
    return redirect(url_for("inbox"))

@app.route("/files/<filename>")
def uploaded_file(filename):
    return send_from_directory(FILES_DIR,filename)

@app.route("/logout")
def logout():
    session.pop("user",None)
    flash("Вы вышли из системы.","success")
    return redirect(url_for("login"))

# ================== Запуск ==================
if __name__=="__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


