import psycopg2
import json
import re
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter

DB_CONFIG = {
    "dbname": "news_rag",
    "user": "tuan",
    "password": "tuan",
    "host": "localhost",
    "port": 5432
}

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

def init_warehouse_schema(cur, conn):
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
        # print("[*] Đang kiểm tra và khởi tạo các bản ghi mặc định (ID 0)...")
        # try:
        #     # 1. Bơm lại bản ghi ID = 0 làm "phao cứu sinh" cho dữ liệu khuyết
        #     cur.execute("""
        #         INSERT INTO dim_time (time_id, date, day, month, year) 
        #         SELECT 0, '1900-01-01', 1, 1, 1900 
        #         WHERE NOT EXISTS (SELECT 1 FROM dim_time WHERE time_id = 0);
        #     """)
            
        #     cur.execute("""
        #         INSERT INTO dim_author (author_id, author_name) 
        #         SELECT 0, 'Unknown' 
        #         WHERE NOT EXISTS (SELECT 1 FROM dim_author WHERE author_id = 0);
        #     """)
            
        #     # 2. Reset Sequence an toàn (Tránh lỗi đếm ID nếu bảng chỉ có mỗi ID 0)
        #     cur.execute("SELECT setval('dim_time_time_id_seq', GREATEST((SELECT MAX(time_id) FROM dim_time), 1));")
        #     cur.execute("SELECT setval('dim_author_author_id_seq', GREATEST((SELECT MAX(author_id) FROM dim_author), 1));")
            
        #     conn.commit()
        # except Exception as e:
        #     conn.rollback()
        #     print(f"[!] Cảnh báo System Init: {e}")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, chunk_overlap=150,
            separators=["\n\n", "\n", ".", " ", ""]
        )

        cur.execute("SELECT url_hash, title, content, url FROM article_metadata")
        rows = cur.fetchall()
        if not rows:
            print("[!] Không có dữ liệu trong article_metadata.")
            return
        
        # Xóa dữ liệu trùng 
        seen_titles = set()
        raw_rows = []
        for row in rows:
            current_title = row[1]
            if current_title not in seen_titles:
                seen_titles.add(current_title)
                raw_rows.append(row)
            else:
                # Nếu muốn xem có bao nhiêu bài trùng bị loại ngay từ vòng gửi xe thì bật dòng này:
                print(f" [DROP] Trùng lặp trong batch: {current_title[:40]}...")
                pass

        print(f"[*] Bắt đầu xử lý {len(raw_rows)} bản ghi (Đã loại bỏ các bản ghi trùng lặp nội bộ)...")

        for url_hash, title, content_raw, url in raw_rows:
            try:
                data = content_raw if isinstance(content_raw, dict) else json.loads(content_raw)

                # Xóa bản ghi thiếu author hoặc publish_date để tránh lỗi khi xử lý
                raw_authors = data.get('author', 'Unknown')
                p_date_str = data.get('publish_date', 'Unknown')
                if raw_authors == "Unknown" or p_date_str == "Unknown" or not p_date_str:
                    print(f" [SKIP] Khuyết thông tin (Author/Date): {title[:40]}...")
                    continue

                cleaned_text = clean_text(data.get('content', ''))
                
                raw_authors = data.get('author', 'Unknown')
                if not raw_authors or raw_authors == "Unknown":
                    author_list = ["Unknown"]
                elif isinstance(raw_authors, str):
                    clean_authors = re.sub(r'\(.*?\)', '', raw_authors)
                    clean_authors = re.split(r'(?i)\s+và\s+', clean_authors)[0]
                    raw_list = re.split(r',|\s*-\s*', clean_authors)
                    author_list = [a.strip() for a in raw_list if a.strip()]
                    if not author_list:
                        author_list = ["Unknown"]
                else:
                    author_list = raw_authors

                domain = url.split('/')[2] if '//' in url else url
                cur.execute("""
                    INSERT INTO dim_source (domain) VALUES (%s) 
                    ON CONFLICT (domain) DO UPDATE SET domain = EXCLUDED.domain 
                    RETURNING source_id
                """, (domain,))
                source_id = cur.fetchone()[0]

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

                cur.execute("""
                    INSERT INTO dim_content (url_hash, content) 
                    VALUES (%s, %s) ON CONFLICT (url_hash) 
                    DO UPDATE SET content = EXCLUDED.content RETURNING content_id
                """, (url_hash, cleaned_text))
                content_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO fact_articles (url_hash, title, source_id, time_id, content_id, content_length)
                    VALUES (%s, %s, %s, %s, %s, %s) 
                    ON CONFLICT (url_hash) DO UPDATE SET title = EXCLUDED.title 
                    RETURNING article_id
                """, (url_hash, title, source_id, time_id, content_id, len(cleaned_text)))
                article_id = cur.fetchone()[0]

                cur.execute("DELETE FROM fact_article_authors WHERE article_id = %s", (article_id,))
                for name in author_list:
                    if name != "Unknown":
                        cur.execute("""
                            INSERT INTO dim_author (author_name) VALUES (%s) 
                            ON CONFLICT (author_name) DO UPDATE SET author_name = EXCLUDED.author_name 
                            RETURNING author_id
                        """, (name,))
                        curr_auth_id = cur.fetchone()[0]
                    
                    cur.execute("INSERT INTO fact_article_authors (article_id, author_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (article_id, curr_auth_id))

                cur.execute("DELETE FROM fact_chunks WHERE article_id = %s", (article_id,))
                chunks = text_splitter.split_text(cleaned_text)
                for i, chunk_text in enumerate(chunks):
                    clean_chunk = chunk_text.lstrip('. ,!?\n\t')
                    if clean_chunk:
                        cur.execute("INSERT INTO fact_chunks (article_id, chunk_index, content) VALUES (%s, %s, %s)", (article_id, i, clean_chunk))

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