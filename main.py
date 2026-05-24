import os
import uuid
import io
import zipfile
import smtplib
import json
from datetime import datetime
from email.message import EmailMessage
from flask import Flask, render_template, request, redirect, url_for, make_response, session, jsonify
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'super_secret_key_direction_2026'

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['ARCHIVE_FOLDER'] = os.path.join('static', 'archive_reports')

try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['ARCHIVE_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"ПОМИЛКА СТВОРЕННЯ ПАПОК: {e}")

GENERAL_PASSWORD = "235711"
ADMIN_PASSWORD = "2026" 
SMTP_PASSWORD = "cdmempvwuytpkrzc"

def get_db_connection():
    conn = sqlite3.connect('new_database.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS objects (id INTEGER PRIMARY KEY, category_id INTEGER, name TEXT, company TEXT, map_url TEXT, position INTEGER DEFAULT 999)''')
        c.execute('''CREATE TABLE IF NOT EXISTS photos (id INTEGER PRIMARY KEY, object_id INTEGER, filename TEXT, upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS work_logs (id INTEGER PRIMARY KEY, object_id INTEGER, user_id TEXT, date TEXT, description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS hours_logs (id INTEGER PRIMARY KEY, object_id INTEGER, user_id TEXT, date TEXT, amount REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS funds_logs (id INTEGER PRIMARY KEY, object_id INTEGER, user_id TEXT, date TEXT, description TEXT, amount REAL, receipt_filename TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS report_archive (id INTEGER PRIMARY KEY, report_id TEXT, requested_by TEXT, period TEXT, sent_to_email TEXT, file_path TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (id INTEGER PRIMARY KEY, user_id TEXT, action_type TEXT, details TEXT, ip_address TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"ПОМИЛКА БАЗИ ДАНИХ ПРИ СТАРТІ: {e}")

init_db()

def log_action(action_type, details=None):
    if details is None: details = {}
    user_id = session.get('user_id', 'Guest')
    if session.get('is_admin'): user_id = 'Admin'
    ip_address = request.remote_addr
    details_json = json.dumps(details, ensure_ascii=False)
    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO audit_logs (user_id, action_type, details, ip_address) VALUES (?, ?, ?, ?)', (user_id, action_type, details_json, ip_address))
        conn.commit()
        conn.close()
    except:
        pass

@app.route('/')
def index():
    if request.cookies.get('general_access') != GENERAL_PASSWORD:
        return render_template('index.html', locked=True)
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    objects = conn.execute('SELECT * FROM objects ORDER BY position ASC, id ASC').fetchall()
    conn.close()
    return render_template('index.html', locked=False, categories=categories, objects=objects)

@app.route('/unlock', methods=['POST'])
def unlock():
    password = request.form.get('password')
    if password == GENERAL_PASSWORD:
        log_action('APP_UNLOCK_SUCCESS')
        resp = make_response(redirect(url_for('index')))
        resp.set_cookie('general_access', password, max_age=60*60*24*365)
        return resp
    log_action('APP_UNLOCK_FAILED')
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    if request.form.get('password') == ADMIN_PASSWORD:
        session['is_admin'] = True
        log_action('ADMIN_LOGIN_SUCCESS')
        return redirect(url_for('admin'))
    log_action('ADMIN_LOGIN_FAILED')
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('is_admin'): return redirect(url_for('index'))
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories').fetchall()
    objects = conn.execute('SELECT * FROM objects ORDER BY position ASC, id ASC').fetchall()
    conn.close()
    return render_template('admin.html', categories=categories, objects=objects)

@app.route('/update', methods=['POST'])
def update_object():
    if not session.get('is_admin'): return redirect(url_for('index'))
    
    obj_id = request.form.get('id')
    cat_id_raw = request.form.get('category_id')
    # ВИПРАВЛЕННЯ: Конвертація в integer для коректного відображення в index.html
    cat_id = int(cat_id_raw) if cat_id_raw and cat_id_raw.isdigit() else 0
    name = request.form.get('name', '')
    company = request.form.get('company', '')
    map_url = request.form.get('map_url', '')
    
    conn = get_db_connection()
    if obj_id == 'new':
        conn.execute('INSERT INTO objects (category_id, name, company, map_url, position) VALUES (?, ?, ?, ?, 0)', (cat_id, name, company, map_url))
        log_action('CREATE_OBJECT', {'name': name})
    else:
        # Оновлюємо також category_id на випадок зміни категорії
        conn.execute('UPDATE objects SET category_id=?, name=?, company=?, map_url=? WHERE id=?', (cat_id, name, company, map_url, obj_id))
        log_action('UPDATE_OBJECT', {'id': obj_id})
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/delete_object/<int:obj_id>', methods=['POST'])
def delete_object(obj_id):
    if not session.get('is_admin'): return "403", 403
    conn = get_db_connection()
    conn.execute('DELETE FROM objects WHERE id=?', (obj_id,))
    conn.commit()
    conn.close()
    log_action('DELETE_OBJECT', {'obj_id': obj_id})
    return "OK", 200

@app.route('/add_category', methods=['POST'])
def add_category():
    if not session.get('is_admin'): return redirect(url_for('index'))
    name = request.form.get('name', 'НОВА КАТЕГОРІЯ') 
    conn = get_db_connection()
    conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    log_action('CREATE_CATEGORY', {'name': name})
    return redirect(url_for('admin'))

@app.route('/update_category', methods=['POST'])
def update_category():
    if not session.get('is_admin'): return "Unauthorized", 403
    cat_id = request.form.get('id')
    name = request.form.get('name')
    conn = get_db_connection()
    conn.execute('UPDATE categories SET name=? WHERE id=?', (name, cat_id))
    conn.commit()
    conn.close()
    log_action('UPDATE_CATEGORY', {'cat_id': cat_id, 'name': name})
    return "OK", 200

@app.route('/delete_category/<int:cat_id>', methods=['POST'])
def delete_category(cat_id):
    if not session.get('is_admin'): return "Unauthorized", 403
    conn = get_db_connection()
    conn.execute('DELETE FROM objects WHERE category_id=?', (cat_id,))
    conn.execute('DELETE FROM categories WHERE id=?', (cat_id,))
    conn.commit()
    conn.close()
    log_action('DELETE_CATEGORY', {'cat_id': cat_id})
    return "OK", 200

@app.route('/reorder_objects', methods=['POST'])
def reorder_objects():
    if not session.get('is_admin'): return "Unauthorized", 403
    data = request.get_json()
    order = data.get('order', [])
    conn = get_db_connection()
    for index, obj_id in enumerate(order):
        conn.execute('UPDATE objects SET position=? WHERE id=?', (index, obj_id))
    conn.commit()
    conn.close()
    log_action('REORDER_OBJECTS')
    return "OK", 200

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    if request.cookies.get('general_access') != GENERAL_PASSWORD: return "403", 403
    file = request.files.get('photo')
    obj_id = request.form.get('object_id')
    if file and obj_id:
        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
        conn = get_db_connection()
        conn.execute('INSERT INTO photos (object_id, filename) VALUES (?, ?)', (obj_id, unique_name))
        conn.commit()
        conn.close()
        log_action('UPLOAD_PHOTO', {'obj_id': obj_id})
        return "OK", 200
    return "Error", 400

@app.route('/get_photos/<int:obj_id>')
def get_photos(obj_id):
    conn = get_db_connection()
    photos = conn.execute('SELECT filename FROM photos WHERE object_id = ? ORDER BY upload_date DESC', (obj_id,)).fetchall()
    conn.close()
    return jsonify([p['filename'] for p in photos])

@app.route('/send_archive', methods=['POST'])
def send_archive():
    data = request.get_json()
    email_to = data.get('email')
    filenames = data.get('filenames', [])
    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in filenames:
                path = os.path.join(app.config['UPLOAD_FOLDER'], f)
                if os.path.exists(path): zf.write(path, arcname=f)
        zip_buffer.seek(0)
        msg = EmailMessage()
        msg['Subject'] = 'Архів фото'
        msg['From'] = 'vnipi83@gmail.com'
        msg['To'] = email_to
        msg.set_content('Архів у вкладенні.')
        msg.add_attachment(zip_buffer.read(), maintype='application', subtype='zip', filename='photos.zip')
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login('vnipi83@gmail.com', SMTP_PASSWORD)
            smtp.send_message(msg)
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route('/submit_work', methods=['POST'])
def submit_work():
    if request.cookies.get('general_access') != GENERAL_PASSWORD: return "403", 403
    d = request.form
    conn = get_db_connection()
    conn.execute('INSERT INTO work_logs (object_id, user_id, date, description) VALUES (?,?,?,?)', (d['object_id'], '', d['date'], d['text']))
    conn.commit()
    conn.close()
    return "OK", 200

@app.route('/submit_hours', methods=['POST'])
def submit_hours():
    if request.cookies.get('general_access') != GENERAL_PASSWORD: return "403", 403
    d = request.form
    conn = get_db_connection()
    conn.execute('INSERT INTO hours_logs (object_id, user_id, date, amount) VALUES (?,?,?,?)', (d['object_id'], '', d['date'], d['amount']))
    conn.commit()
    conn.close()
    return "OK", 200

@app.route('/submit_funds', methods=['POST'])
def submit_funds():
    if request.cookies.get('general_access') != GENERAL_PASSWORD: return "403", 403
    d = request.form
    receipt = request.files.get('receipt')
    r_name = None
    if receipt:
        r_name = f"receipt_{uuid.uuid4().hex}_{secure_filename(receipt.filename)}"
        receipt.save(os.path.join(app.config['UPLOAD_FOLDER'], r_name))
    conn = get_db_connection()
    conn.execute('INSERT INTO funds_logs (object_id, user_id, date, description, amount, receipt_filename) VALUES (?,?,?,?,?,?)',
                 (d['object_id'], '', d['date'], d['description'], d['amount'], r_name))
    conn.commit()
    conn.close()
    return "OK", 200

@app.route('/api/report_data', methods=['POST'])
def get_report_data():
    if request.cookies.get('general_access') != GENERAL_PASSWORD: return "403", 403
    data = request.get_json()
    oid = data['object_id']
    s_date = data['start_date']
    e_date = data['end_date']
    rtype = data['report_type']
    conn = get_db_connection()
    res = {'work': [], 'hours': [], 'funds': []}
    def fetch(tbl):
        if oid == 'all':
            return conn.execute(f"SELECT {tbl}.*, objects.name as obj_name, objects.company as obj_company FROM {tbl} JOIN objects ON {tbl}.object_id = objects.id WHERE date BETWEEN ? AND ? ORDER BY object_id, date ASC", (s_date, e_date)).fetchall()
        return conn.execute(f"SELECT {tbl}.*, objects.name as obj_name, objects.company as obj_company FROM {tbl} JOIN objects ON {tbl}.object_id = objects.id WHERE object_id=? AND date BETWEEN ? AND ? ORDER BY date ASC", (oid, s_date, e_date)).fetchall()
    if rtype in ['all', 'work']: res['work'] = [dict(r) for r in fetch('work_logs')]
    if rtype in ['all', 'hours']: res['hours'] = [dict(r) for r in fetch('hours_logs')]
    if rtype in ['all', 'funds']: res['funds'] = [dict(r) for r in fetch('funds_logs')]
    if oid != 'all':
        obj = conn.execute('SELECT name, company FROM objects WHERE id=?', (oid,)).fetchone()
        if obj: res['object_info'] = dict(obj)
    conn.close()
    return jsonify(res)

@app.route('/api/save_report', methods=['POST'])
def save_report():
    if request.cookies.get('general_access') != GENERAL_PASSWORD: return "403", 403
    f = request.files['pdf']
    fname = f"report_{uuid.uuid4().hex}.pdf"
    f.save(os.path.join(app.config['ARCHIVE_FOLDER'], fname))
    conn = get_db_connection()
    conn.execute('INSERT INTO report_archive (report_id, requested_by, period, file_path) VALUES (?,?,?,?)', (fname, 'Guest', request.form['period'], fname))
    conn.commit()
    conn.close()
    return jsonify({"filename": fname})

@app.route('/api/email_report', methods=['POST'])
def email_report():
    if request.cookies.get('general_access') != GENERAL_PASSWORD: return "403", 403
    data = request.get_json()
    path = os.path.join(app.config['ARCHIVE_FOLDER'], data['filename'])
    msg = EmailMessage()
    msg['Subject'] = 'Звіт'
    msg['From'] = 'vnipi83@gmail.com'
    msg['To'] = data['email']
    with open(path, 'rb') as f: msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename='report.pdf')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login('vnipi83@gmail.com', SMTP_PASSWORD)
        smtp.send_message(msg)
    return "OK", 200

@app.route('/sw.js')
def sw():
    response = make_response(app.send_static_file('sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000)