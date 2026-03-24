import psycopg2
import json
import re
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- CẤU HÌNH KẾT NỐI ---
DB_CONFIG = {
    "dbname": "news_rag",
    "user": "tuan",
    "password": "tuan",
    "host": "localhost",
    "port": 5432
}

# ----- HÀM HỖ TRỢ LÀM SẠCH DỮ LIỆU TRONG BƯỚC TRANFORM -----   
def clean_text(text):
    if not text: return ""
    text = re.sub(r'\s+', ' ', text) 
    junk_patterns = [
        r"Chia sẻ bài viết qua email", r"Ảnh:.*?\.", r"Video:.*?\.",
        r"Độc giả.*?\.", r"Bản quyền thuộc về.*", r"Hãy gửi câu hỏi về.*"
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()

# ----- HÀM KHỞI TẠO TỰ ĐỘNG CẤU TRÚC BẢNG WAREHOUSE -----
def init_warehouse_schema(cur, conn):
    """Đọc file SQL và khởi tạo cấu trúc bảng nếu chưa có"""
    try:
        print("[*] Đang kiểm tra và cập nhật cấu trúc Warehouse từ warehouse.sql...")
        with open('warehouse.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
            cur.execute(sql_script)
            conn.commit()
            print("[SUCCESS] Đã nạp cấu trúc Warehouse thành công.")
    except FileNotFoundError:
        print("[ERROR] Không tìm thấy file warehouse.sql. Hãy đảm bảo file nằm cùng thư mục.")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Lỗi khi nạp warehouse.sql: {e}")

def run_etl_warehouse():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        init_warehouse_schema(cur, conn)
        # KHỞI TẠO HỆ THỐNG (SYSTEM INIT) 
        print("[*] Đang kiểm tra và khởi tại các bản ghi mặc định (ID 0)...")
        try:
            cur.execute("SELECT setval('dim_time_time_id_seq', COALESCE((SELECT MAX(time_id) FROM dim_time), 0), true)")
            cur.execute("SELECT setval('dim_author_author_id_seq', COALESCE((SELECT MAX(author_id) FROM dim_author), 0), true)")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[!] Cảnh báo Sync Sequence: {e}")

        # Khởi tạo cấu hình cho 1 chunk gồm size = 800 ký tự, overlap = 150 ký tự, và các separator ưu tiên để tách.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=150,
            separators=["\n\n", "\n", ".", " ", ""]
        )

        # ----- 1. EXTRACT ------
        # Lấy tất cả dữ liệu từ bảng article_metadata
        cur.execute("SELECT url_hash, title, content, url FROM article_metadata")
        rows = cur.fetchall()
        if not rows:
            print("[!] Không có dữ liệu trong article_metadata.")
            return

        for url_hash, title, content_raw, url in rows:
            try:
                data = content_raw if isinstance(content_raw, dict) else json.loads(content_raw)
                
                # ----- 2. TRANSFORM -----
                # Làm sạch content - chỉ xử lý xuống dòng, khoảng trắng thừa và các pattern rác. Ảnh thừa và link lạ đã được loại bỏ ở spider.py.
                # Chia content thành các chunk nhỏ hơn.
                cleaned_text = clean_text(data.get('content', ''))
                
                # Tách tên tác giả nếu có nhiều hơn một người, trường hợp không có thì để "Unknown"
                raw_authors = data.get('author', 'Unknown')
                if not raw_authors or raw_authors == "Unknown":
                    author_list = ["Unknown"]
                elif isinstance(raw_authors, str):
                    author_list = [a.strip() for a in re.split(r' - |, | và ', raw_authors) if a.strip()]
                else:
                    author_list = raw_authors

                # --- LOAD DIM_SOURCE ---
                domain = url.split('/')[2] if '//' in url else url
                cur.execute("""
                    INSERT INTO dim_source (domain) VALUES (%s) 
                    ON CONFLICT (domain) DO UPDATE SET domain = EXCLUDED.domain 
                    RETURNING source_id
                """, (domain,))
                source_id = cur.fetchone()[0]

                # --- LOAD DIM_TIME ---
                p_date_str = data.get('publish_date', 'Unknown')
                time_id = 0 
                if p_date_str != "Unknown" and p_date_str:
                    try:
                        dt = datetime.strptime(p_date_str, "%Y-%m-%d %H:%M:%S")
                        cur.execute("""
                            INSERT INTO dim_time (date, day, month, year) 
                            VALUES (%s, %s, %s, %s) ON CONFLICT (date) 
                            DO UPDATE SET date = EXCLUDED.date RETURNING time_id
                        """, (dt.date(), dt.day, dt.month, dt.year))
                        time_id = cur.fetchone()[0]
                    except: time_id = 0

                # --- LOAD DIM_CONTENT ---
                cur.execute("""
                    INSERT INTO dim_content (url_hash, content) 
                    VALUES (%s, %s) ON CONFLICT (url_hash) 
                    DO UPDATE SET content = EXCLUDED.content RETURNING content_id
                """, (url_hash, cleaned_text))
                content_id = cur.fetchone()[0]

                # --- LOAD FACT_ARTICLES ---
                cur.execute("""
                    INSERT INTO fact_articles (url_hash, title, source_id, time_id, content_id, content_length)
                    VALUES (%s, %s, %s, %s, %s, %s) 
                    ON CONFLICT (url_hash) DO UPDATE SET title = EXCLUDED.title 
                    RETURNING article_id
                """, (url_hash, title, source_id, time_id, content_id, len(cleaned_text)))
                article_id = cur.fetchone()[0]

                # --- LOAD FACT_ARTICLE_AUTHORS ---
                cur.execute("DELETE FROM fact_article_authors WHERE article_id = %s", (article_id,))
                for name in author_list:
                    curr_auth_id = 0
                    if name != "Unknown":
                        cur.execute("""
                            INSERT INTO dim_author (author_name) VALUES (%s) 
                            ON CONFLICT (author_name) DO UPDATE SET author_name = EXCLUDED.author_name 
                            RETURNING author_id
                        """, (name,))
                        curr_auth_id = cur.fetchone()[0]
                    
                    cur.execute("INSERT INTO fact_article_authors (article_id, author_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (article_id, curr_auth_id))

                # --- LOAD FACT_CHUNKS ---
                cur.execute("DELETE FROM fact_chunks WHERE article_id = %s", (article_id,))
                chunks = text_splitter.split_text(cleaned_text) # Tách chunk
                for i, chunk_text in enumerate(chunks):
                    cur.execute("INSERT INTO fact_chunks (article_id, chunk_index, content) VALUES (%s, %s, %s)", (article_id, i, chunk_text))
                
                conn.commit()
                print(f" [OK] Title: {title[:40]}...")

            except Exception as e:
                conn.rollback()
                print(f" [ERROR] {title[:20] if title else 'Unknown'}: {e}")

        cur.close()
        conn.close()
        print("\n[*] Hệ thống Warehouse đã sẵn sàng!")

    except Exception as e:
        print(f"[!] Lỗi kết nối: {e}")

if __name__ == "__main__":
    run_etl_warehouse()