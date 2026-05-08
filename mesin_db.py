import psycopg2

# ==========================================
# GANTI PAKAI URL DARI NEON.TECH MILIK LU
# Contoh: "postgresql://neondb_owner:P4ssW0rdRahasi4@ep-kuda-terbang-12345.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
# ==========================================
DATABASE_URL = "postgresql://neondb_owner:npg_Vimk9fMlI6rL@ep-floral-brook-aotd30k2.c-2.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

def inisiasi_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Tabel target web (Postgres pakai SERIAL buat Auto Increment)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS target_web (
                id SERIAL PRIMARY KEY,
                nama VARCHAR(255) NOT NULL,
                url VARCHAR(255) NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Tabel log monitoring (Postgres pakai TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS log_monitoring (
                id SERIAL PRIMARY KEY,
                id_web INTEGER,
                status_code INTEGER,
                waktu_respon REAL,
                diagnosa TEXT,
                waktu_cek TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(id_web) REFERENCES target_web(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ [Database] PostgreSQL Cloud berhasil diinisiasi!")
    except Exception as e:
        print(f"❌ [Database] Gagal konek ke PostgreSQL: {e}")

if __name__ == '__main__':
    inisiasi_db()