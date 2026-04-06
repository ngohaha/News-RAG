import json
import hashlib
import psycopg2
from confluent_kafka import Consumer

# --- CẤU HÌNH ---
PG_CONFIG = {
    "dbname": "news_rag",
    "user": "tuan",
    "password": "tuan",
    "host": "localhost"
}

# Kết nối PostgreSQL
def get_postgres_conn():
    return psycopg2.connect(**PG_CONFIG)

# Kafka config
conf = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'news_rag_group_oithoichec', # Đổi tên group ở đây
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(conf)
consumer.subscribe(['news_raw'])


def start_processing():
    print(" [Consumer] Đang chạy pipeline PostgreSQL-only...")
    
    # Khởi tạo kết nối ban đầu
    pg_conn = get_postgres_conn()
    
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                # Đừng print liên tục ở đây để tránh trôi log của Spider
                continue

            if msg.error():
                print(f" [Kafka Error]: {msg.error()}")
                continue

            try:
                # Decode message
                raw_data = msg.value().decode('utf-8')
                data = json.loads(raw_data)
                
                url = data.get('url', '')
                title = data.get('title', 'Unknown Title')
                author = data.get('author', 'Unknown')
                publish_date = data.get('publish_date', None)
                content = data.get('content', '') # Lấy content riêng ra

                if not url: continue

                url_hash = hashlib.sha256(url.encode()).hexdigest()

                with pg_conn.cursor() as cursor:
                    # Logic chuẩn: INSERT hoặc bỏ qua, không cần RETURNING phức tạp
                    cursor.execute("""
                        INSERT INTO article_metadata (url_hash, url, title, content, author, publish_date)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url_hash) DO NOTHING;
                    """, (url_hash, url, title, content, author, publish_date))
                
                # Commit ngay lập tức cho từng bài để đảm bảo an toàn dữ liệu
                pg_conn.commit()
                print(f"[SUCCESS] {title[:50]}...")

            except psycopg2.InterfaceError:
                # Nếu kết nối DB bị đứt, hãy thử kết nối lại thay vì sập luôn
                print("[DB] Mất kết nối, đang thử kết nối lại...")
                pg_conn = get_postgres_conn()
            except Exception as e:
                pg_conn.rollback()
                print(f"[ERROR] Bỏ qua bài do lỗi: {e}")

    except KeyboardInterrupt:
        print("\n[Consumer] Đang dừng...")
    finally:
        consumer.close()
        if pg_conn: pg_conn.close()


if __name__ == "__main__":
    start_processing()