import telebot
from telebot import types
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import json
import os
import uuid
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# --- CONFIGURATION (Environment Variables for Render) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7992380671:AAE9euDdBd1rQ93RkYhWlbGYUvoopVR-L3Q")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "freemessagebomber@gmail.com")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "dkwu zjdt pzkv siup")
PORT = int(os.environ.get("PORT", 8080))
HOST_URL = os.environ.get("HOST_URL", "http://127.0.0.1:8080") # Render এ আপনার ওয়েবসাইটের লিংক দিবেন

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
CORS(app)

# --- DIRECTORY SETUP ---
# Render এ ডাটা সেভ রাখার জন্য একটি নির্দিষ্ট ফোল্ডার
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
USER_DATA_FILE = os.path.join(DATA_DIR, "users.json")
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DATABASE FUNCTIONS ---
def load_users():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_DATA_FILE, "w") as f:
        json.dump(users, f, indent=4)

def get_dev_by_api_key(api_key):
    users = load_users()
    for email, info in users.items():
        if info.get('api_key') == api_key:
            return email, info
    return None, None

# --- EMAIL OTP FUNCTION ---
def send_otp_email(receiver_email, otp):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"CloudNest <{SENDER_EMAIL}>"
        msg['To'] = receiver_email
        msg['Subject'] = "Your CloudNest OTP Code"
        body = f"<h2>Welcome to CloudNest!</h2><p>Your verification code is: <strong>{otp}</strong></p>"
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

# ==========================================
#         FLASK API SERVER FOR APP
# ==========================================

# 1. DATABASE API
@app.route('/api/db', methods=['POST'])
def api_db():
    data = request.json
    api_key = data.get('api_key')
    action = data.get('action')
    key = data.get('key', 'default')
    payload = data.get('data', '')

    dev_email, dev_info = get_dev_by_api_key(api_key)
    if not dev_email: return jsonify({"status": "error", "message": "Invalid API Key."})

    db_file = os.path.join(DATA_DIR, f"{dev_info['api_key']}_db.json")
    db_data = {}
    if os.path.exists(db_file):
        with open(db_file, "r") as f: db_data = json.load(f)

    if action == 'save':
        db_data[key] = payload
        with open(db_file, "w") as f: json.dump(db_data, f)
        return jsonify({"status": "success", "message": "Data saved!"})
    elif action == 'load':
        return jsonify({"status": "success", "data": db_data.get(key, "")})

    return jsonify({"status": "error", "message": "Invalid action."})

# 2. AUTHENTICATION API
@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.json
    api_key = data.get('api_key')
    action = data.get('action')
    username = data.get('username')
    password = data.get('password')

    dev_email, dev_info = get_dev_by_api_key(api_key)
    if not dev_email: return jsonify({"status": "error", "message": "Invalid API Key."})

    auth_file = os.path.join(DATA_DIR, f"{dev_info['api_key']}_auth.json")
    auth_data = {}
    if os.path.exists(auth_file):
        with open(auth_file, "r") as f: auth_data = json.load(f)

    if action == 'register':
        if username in auth_data:
            return jsonify({"status": "error", "message": "User exists!"})
        auth_data[username] = {"password": password}
        with open(auth_file, "w") as f: json.dump(auth_data, f)
        return jsonify({"status": "success", "message": "Registered successfully!"})
    elif action == 'login':
        if username in auth_data and auth_data[username]['password'] == password:
            return jsonify({"status": "success", "message": "Logged in successfully!"})
        return jsonify({"status": "error", "message": "Wrong credentials."})
    
    return jsonify({"status": "error", "message": "Invalid action."})

# 3. FILE UPLOAD API
@app.route('/api/upload', methods=['POST'])
def upload_file():
    api_key = request.form.get('api_key')
    dev_email, dev_info = get_dev_by_api_key(api_key)
    if not dev_email: return jsonify({"status":"error", "message":"Invalid API key"})

    if 'file' not in request.files: return jsonify({"status":"error", "message":"No file uploaded"})
    file = request.files['file']
    if file.filename == '': return jsonify({"status":"error", "message":"Empty file"})
    
    filename = secure_filename(file.filename)
    unique_filename = f"{dev_info['api_key']}_{uuid.uuid4().hex[:8]}_{filename}"
    file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
    
    # Return Public URL
    host = HOST_URL.rstrip('/')
    file_url = f"{host}/uploads/{unique_filename}"
    return jsonify({"status": "success", "url": file_url})

# 4. LOAD FILE API
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ==========================================
#         TELEGRAM BOT LOGIC
# ==========================================
user_sessions = {}

@bot.message_handler(commands=['start', 'restart'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Create a new account", "Login")
    bot.send_message(message.chat.id, "Welcome to ☁️ CloudNest Backend Manager!", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id
    text = message.text
    users = load_users()

    if chat_id in user_sessions and user_sessions[chat_id].get('logged_in'):
        email = user_sessions[chat_id]['email']
        user_info = users[email]
        step = user_sessions[chat_id].get('step')

        # Edit User Password Logic
        if step == 'edit_app_user_password':
            editing_user = user_sessions[chat_id].get('editing_user')
            auth_file = os.path.join(DATA_DIR, f"{user_info['api_key']}_auth.json")
            if os.path.exists(auth_file):
                with open(auth_file, "r") as f: auth_data = json.load(f)
                if editing_user in auth_data:
                    auth_data[editing_user]['password'] = text
                    with open(auth_file, "w") as f: json.dump(auth_data, f)
                    bot.send_message(chat_id, f"✅ Password for `{editing_user}` updated successfully!", parse_mode="Markdown")
            user_sessions[chat_id]['step'] = None
            user_sessions[chat_id].pop('editing_user', None)
            return

        # Main Menus
        if text == "Database":
            db_file = os.path.join(DATA_DIR, f"{user_info['api_key']}_db.json")
            if os.path.exists(db_file):
                with open(db_file, "r") as f: db_data = json.load(f)
                msg = "🗄 **Your Database Entries:**\n\n"
                for key, val in db_data.items():
                    msg += f"🔑 `{key}` : {str(val)[:20]}...\n"
                bot.send_message(chat_id, msg, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, "🗄 **Database is Empty!**", parse_mode="Markdown")

        elif text == "Authentication":
            auth_file = os.path.join(DATA_DIR, f"{user_info['api_key']}_auth.json")
            if os.path.exists(auth_file):
                with open(auth_file, "r") as f: auth_data = json.load(f)
                if auth_data:
                    markup = types.InlineKeyboardMarkup()
                    for username, details in auth_data.items():
                        markup.add(types.InlineKeyboardButton(text=f"👤 {username} (Edit)", callback_data=f"edit_user_{username}"))
                    bot.send_message(chat_id, "👥 **App Users:**\nClick a user to edit their password:", parse_mode="Markdown", reply_markup=markup)
                else:
                    bot.send_message(chat_id, "No users registered yet.")
            else:
                bot.send_message(chat_id, "No users registered yet.")

        elif text == "Project Settings":
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("💻 Database API Code", callback_data="code_db"))
            markup.add(types.InlineKeyboardButton("💻 Auth API Code", callback_data="code_auth"))
            markup.add(types.InlineKeyboardButton("📁 File Upload Code", callback_data="code_upload"))
            bot.send_message(chat_id, f"⚙️ **Your API Key:**\n`{user_info['api_key']}`\n\n_Click below to copy your HTML/JS code!_", parse_mode="Markdown", reply_markup=markup)
            
        elif text == "Logout":
            user_sessions.pop(chat_id, None)
            send_welcome(message)
        return

    # Registration & Login Logic
    if text == "Create a new account":
        bot.send_message(chat_id, "Please enter your Gmail (@gmail.com):", reply_markup=types.ReplyKeyboardRemove())
        user_sessions[chat_id] = {'step': 'wait_email'}
    elif text == "Login":
        bot.send_message(chat_id, "Enter your Email:", reply_markup=types.ReplyKeyboardRemove())
        user_sessions[chat_id] = {'step': 'login_email'}
    elif chat_id in user_sessions:
        step = user_sessions[chat_id].get('step')
        if step == 'wait_email':
            if text.endswith("@gmail.com"):
                otp = str(random.randint(100000, 999999))
                user_sessions[chat_id]['temp_email'] = text
                user_sessions[chat_id]['otp'] = otp
                bot.send_message(chat_id, "Sending OTP... Please wait.")
                if send_otp_email(text, otp):
                    bot.send_message(chat_id, "✅ OTP Sent! Enter the 6-digit code:")
                    user_sessions[chat_id]['step'] = 'wait_otp'
                else:
                    bot.send_message(chat_id, "❌ Email Error!")
        elif step == 'wait_otp':
            if text == user_sessions[chat_id]['otp']:
                bot.send_message(chat_id, "✅ Verified! Enter a password:")
                user_sessions[chat_id]['step'] = 'wait_password'
        elif step == 'wait_password':
            email = user_sessions[chat_id]['temp_email']
            api_key = "cn_" + str(uuid.uuid4()).replace("-", "")
            users[email] = {"password": text, "api_key": api_key, "telegram_id": chat_id}
            save_users(users)
            bot.send_message(chat_id, "🎉 Account Created! /start to Login.")
            user_sessions.pop(chat_id, None)
        elif step == 'login_email':
            if text in users:
                user_sessions[chat_id]['temp_email'] = text
                bot.send_message(chat_id, "Enter your password:")
                user_sessions[chat_id]['step'] = 'login_pass'
        elif step == 'login_pass':
            email = user_sessions[chat_id]['temp_email']
            if users[email]['password'] == text:
                user_sessions[chat_id] = {'logged_in': True, 'email': email}
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                markup.add("Database", "Authentication", "Project Settings", "Logout")
                bot.send_message(chat_id, "✅ Login Successful!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    if chat_id not in user_sessions or not user_sessions[chat_id].get('logged_in'):
        bot.answer_callback_query(call.id, "Please login first.")
        return

    email = user_sessions[chat_id]['email']
    user_info = load_users().get(email)
    api_key = user_info['api_key']
    host = HOST_URL.rstrip('/')

    if call.data == "code_db":
        code = f"""// --- DATA SAVE ---
fetch('{host}/api/db', {{
  method: 'POST',
  headers: {{'Content-Type': 'application/json'}},
  body: JSON.stringify({{api_key: '{api_key}', action: 'save', key: 'message_1', data: 'Hello World'}})
}});

// --- DATA LOAD ---
fetch('{host}/api/db', {{
  method: 'POST',
  headers: {{'Content-Type': 'application/json'}},
  body: JSON.stringify({{api_key: '{api_key}', action: 'load', key: 'message_1'}})
}}).then(res => res.json()).then(console.log);"""
        bot.send_message(chat_id, f"**Database API Code:**\n```javascript\n{code}\n```", parse_mode="Markdown")
        
    elif call.data == "code_upload":
        code = f"""// HTML: <input type="file" id="fileInput">
const fileInput = document.getElementById('fileInput');
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('api_key', '{api_key}');

// --- FILE UPLOAD (Image/Video/APK) ---
fetch('{host}/api/upload', {{
  method: 'POST',
  body: formData
}}).then(res => res.json()).then(data => {{
    console.log('File URL:', data.url); // Use this URL to load the file!
}});"""
        bot.send_message(chat_id, f"**File Upload API Code:**\n```javascript\n{code}\n```", parse_mode="Markdown")

    elif call.data == "code_auth":
        code = f"""// --- REGISTER USER ---
fetch('{host}/api/auth', {{
  method: 'POST',
  headers: {{'Content-Type': 'application/json'}},
  body: JSON.stringify({{api_key: '{api_key}', action: 'register', username: 'user1', password: '123'}})
}});

// --- LOGIN USER ---
fetch('{host}/api/auth', {{
  method: 'POST',
  headers: {{'Content-Type': 'application/json'}},
  body: JSON.stringify({{api_key: '{api_key}', action: 'login', username: 'user1', password: '123'}})
}}).then(res => res.json()).then(console.log);"""
        bot.send_message(chat_id, f"**Auth API Code:**\n```javascript\n{code}\n```", parse_mode="Markdown")

    elif call.data.startswith("edit_user_"):
        username = call.data.replace("edit_user_", "")
        user_sessions[chat_id]['editing_user'] = username
        user_sessions[chat_id]['step'] = 'edit_app_user_password'
        bot.send_message(chat_id, f"✏️ Enter new password for app user `{username}`:", parse_mode="Markdown")


# --- RUN SYSTEM ---
def run_api_server():
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_api_server)
    server_thread.start()
    print("Telegram Bot and API Server are running...")
    bot.polling(non_stop=True)
