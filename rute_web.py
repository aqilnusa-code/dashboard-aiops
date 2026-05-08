from flask import Flask, render_template, request, redirect, url_for, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import psycopg2
from psycopg2.extras import RealDictCursor
import random
import requests
import socket
import google.generativeai as genai
from urllib.parse import urlparse
import logging

app = Flask(__name__)

# ==========================================
# FITUR BARU: SILENCER (PEREDAM LOG TERMINAL)
# ==========================================
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ==========================================
# KONFIGURASI GEMINI API AI
# ==========================================
GEMINI_API_KEY = "AIzaSyAy1RZc25RrOB0--US1dHhsATUQ_cTVhmE"
genai.configure(api_key=GEMINI_API_KEY)
model_ai = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# KONFIGURASI TELEGRAM BOT
# ==========================================
TOKEN = '8656572451:AAGhdFLvaT7CkwHHSYlP4Y4H-KumOmzvCN8'
TELEGRAM_CHAT_ID = "5075659751"

# ==========================================
# DATABASE POSTGRESQL (DARI NEON.TECH)
# ==========================================
# WAJIB GANTI PAKAI URL NEON LU SENDIRI!!
DATABASE_URL = "postgresql://neondb_owner:npg_Vimk9fMlI6rL@ep-floral-brook-aotd30k2.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": pesan,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
        print("✅ Alert Telegram berhasil dikirim!")
    except Exception as e:
        print("❌ Gagal mengirim pesan Telegram:", e)

# ==========================================
# MESIN AI ANALYST
# ==========================================
def analisa_insiden_ai(nama_web, url, status_code, diagnosa_dasar):
    prompt = f"""
    Kamu adalah seorang Senior DevOps Engineer yang ahli. 
    Sebuah server sedang mengalami insiden DOWN saat di-ping oleh sistem monitoring.
    
    Data Insiden:
    - Nama Target: {nama_web}
    - URL: {url}
    - HTTP Status Code: {status_code}
    - Diagnosa Awal Sistem: {diagnosa_dasar}
    
    Tugas:
    Berikan analisa singkat (maksimal 2 paragraf pendek) mengenai kemungkinan penyebab teknis spesifik dari error ini. 
    Lalu, berikan 2 langkah rekomendasi teknis (action plan) yang harus segera dilakukan oleh SysAdmin.
    Gunakan bahasa Indonesia yang santai, tegas, dan profesional (gunakan kata sapaan "Bro/Bos").
    """
    try:
        response = model_ai.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"❌ AI Gagal memproses analisa: {e}"

# ==========================================
# MESIN WORKER AIOps & NOTIFIKASI
# ==========================================
def cek_kesehatan_web():
    with app.app_context():
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT id, nama, url FROM target_web WHERE is_active = 1 OR is_active IS NULL")
        target_list = cur.fetchall()

        if len(target_list) == 0:
            cur.close()
            conn.close()
            return

        for target in target_list:
            id_web, nama_web, url = target['id'], target['nama'], target['url']
            print(f"🔍 [Ping] Menembak target aktif: {nama_web}...")
            
            diagnosa = "Aman"
            status_code = 0
            waktu_respon = 0.0

            cur.execute('SELECT status_code FROM log_monitoring WHERE id_web = %s ORDER BY waktu_cek DESC LIMIT 1', (id_web,))
            last_log = cur.fetchone()
            
            status_sebelumnya = last_log['status_code'] if last_log else 200 
            web_sebelumnya_error = status_sebelumnya >= 400 or status_sebelumnya == 0

            try:
                response = requests.get(url, timeout=5)
                status_code = response.status_code
                waktu_respon = round(response.elapsed.total_seconds() * 1000, 2)
                
                if status_code >= 500:
                    diagnosa = "Aplikasi Backend Error (Crash / Bug di Server)"
                elif status_code >= 400:
                    diagnosa = "Client Error - Rute Web Ditolak atau Tidak Ditemukan"
                    
            except requests.exceptions.ConnectionError:
                waktu_respon = 0.0
                domain = urlparse(url).netloc
                try:
                    socket.gethostbyname(domain)
                    diagnosa = "Server Down / Port Tertutup / Diblokir Firewall"
                except socket.gaierror:
                    diagnosa = "DNS Error / Nama Domain Tidak Terdaftar"
            except requests.exceptions.Timeout:
                status_code = 408
                waktu_respon = 5000.0
                diagnosa = "Koneksi Timeout (Server Terlalu Lemot / Sibuk)"
            except Exception as e:
                diagnosa = "System Error Tidak Dikenal"

            web_sekarang_error = status_code >= 400 or status_code == 0

            if web_sekarang_error and not web_sebelumnya_error:
                print(f"🤖 [AI] Meminta AI menganalisa insiden di {nama_web}...")
                hasil_analisa_ai = analisa_insiden_ai(nama_web, url, status_code, diagnosa)
                
                pesan_alert = (
                    f"🚨 *ALERT: WEB DOWN!* 🚨\n\n"
                    f"*Target:* {nama_web}\n"
                    f"*URL:* {url}\n"
                    f"*Status:* {status_code} Error\n"
                    f"*Diagnosa Awal:* {diagnosa}\n\n"
                    f"🧠 *ANALISA AIOPS (GEMINI):*\n"
                    f"-----------------------------------\n"
                    f"{hasil_analisa_ai}"
                )
                kirim_telegram(pesan_alert)
            
            elif not web_sekarang_error and web_sebelumnya_error:
                pesan_recovery = (
                    f"✅ *RECOVERY: WEB KEMBALI NORMAL!* ✅\n\n"
                    f"*Target:* {nama_web}\n"
                    f"*URL:* {url}\n"
                    f"*Status:* 200 OK\n"
                    f"*Response:* {waktu_respon} ms\n\n"
                    f"_Server sudah berjalan lancar kembali._"
                )
                kirim_telegram(pesan_recovery)

            cur.execute('''
                INSERT INTO log_monitoring (id_web, status_code, waktu_respon, diagnosa) 
                VALUES (%s, %s, %s, %s)
            ''', (id_web, status_code, waktu_respon, diagnosa))

        conn.commit()
        cur.close()
        conn.close()
        
        print(f"⚡ [AIOps] Analisa selesai. Total {len(target_list)} web aktif berhasil dicek.")

def bersihkan_log_lama():
    with app.app_context():
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            # Pake INTERVAL khas PostgreSQL buat hapus data
            cur.execute("DELETE FROM log_monitoring WHERE waktu_cek <= NOW() - INTERVAL '7 days'")
            jumlah_dihapus = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            if jumlah_dihapus > 0:
                print(f"🧹 [Housekeeping] Sukses menyapu {jumlah_dihapus} log usang! Database kembali langsing.")
            else:
                print("🧹 [Housekeeping] Cek rutin: Tidak ada log usang yang perlu dihapus hari ini.")
        except Exception as e:
            print(f"❌ [Housekeeping] Gagal melakukan pembersihan database: {e}")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=cek_kesehatan_web, trigger="interval", seconds=10)
scheduler.add_job(func=bersihkan_log_lama, trigger="interval", days=1)
scheduler.start()

# ==========================================
# RUTE WEB UTAMA & API
# ==========================================
@app.route('/')
def home():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM target_web ORDER BY id ASC')
    targets = cur.fetchall()
    cur.close()
    conn.close()
    
    ucapan_random = [
        "Satu langkah menuju kemudahan, sistem termonitor aman! 🚀",
        "Jangan lupa ngopi, biarkan server yang kerja keras! ☕",
        "Error adalah teman, debugging adalah jalan ninjanya! 💡",
        "Dashboard on point, sat set sat set kelar! 🔥"
    ]
    pesan_semangat = random.choice(ucapan_random)
    return render_template('index.html', targets=targets, pesan=pesan_semangat)

@app.route('/tambah', methods=['POST'])
def tambah_target():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO target_web (nama, url) VALUES (%s, %s)', (request.form['nama'], request.form['url']))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('home'))

@app.route('/hapus/<int:id_target>')
def hapus_target(id_target):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM log_monitoring WHERE id_web = %s', (id_target,))
    cur.execute('DELETE FROM target_web WHERE id = %s', (id_target,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('home'))

@app.route('/toggle/<int:id_target>')
def toggle_target(id_target):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT is_active FROM target_web WHERE id = %s', (id_target,))
    target = cur.fetchone()
    
    status_sekarang = target['is_active'] if target['is_active'] is not None else 1
    new_status = 0 if status_sekarang == 1 else 1
    
    if new_status == 1:
        print(f"♻️ [Reset] Web {id_target} dinyalakan kembali. Membersihkan riwayat lama...")
        cur.execute('DELETE FROM log_monitoring WHERE id_web = %s', (id_target,))
    
    cur.execute('UPDATE target_web SET is_active = %s WHERE id = %s', (new_status, id_target))
    conn.commit()
    cur.close()
    conn.close()
    
    return redirect(url_for('home'))

@app.route('/api/logs')
def api_logs():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        WITH RankedLogs AS (
            SELECT 
                t.id as id_web, t.nama, t.url, t.is_active, 
                l.status_code, l.waktu_respon, l.diagnosa, l.waktu_cek,
                ROW_NUMBER() OVER(PARTITION BY t.id ORDER BY l.waktu_cek DESC) as rn,
                (SELECT COUNT(*) FROM log_monitoring WHERE id_web = t.id) as total_ping,
                (SELECT COUNT(*) FROM log_monitoring WHERE id_web = t.id AND status_code = 200) as ping_sukses
            FROM target_web t
            JOIN log_monitoring l ON t.id = l.id_web
        )
        SELECT id_web, nama, url, is_active, status_code, waktu_respon, diagnosa, 
               TO_CHAR(waktu_cek, 'YYYY-MM-DD HH24:MI:SS') as waktu_cek, total_ping, ping_sukses
        FROM RankedLogs
        WHERE rn = 1
        ORDER BY waktu_cek DESC
    ''')
    log_data = cur.fetchall()
    cur.close()
    conn.close()
    
    hasil = []
    for data in log_data:
        if data['total_ping'] > 0:
            sla = (data['ping_sukses'] / data['total_ping']) * 100
            data['sla'] = round(sla, 2)
        else:
            data['sla'] = 100.00
        hasil.append(data)
    return jsonify(hasil)

@app.route('/api/chart/<int:id_web>')
def api_chart(id_web):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('''
        SELECT TO_CHAR(waktu_cek, 'YYYY-MM-DD HH24:MI:SS') as waktu_cek, waktu_respon
        FROM log_monitoring
        WHERE id_web = %s
        ORDER BY waktu_cek DESC LIMIT 15
    ''', (id_web,))
    log_data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(log_data[::-1])

if __name__ == '__main__':
    import mesin_db
    mesin_db.inisiasi_db()
    app.run(debug=True, port=5000, use_reloader=False)