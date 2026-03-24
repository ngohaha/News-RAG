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
    'group.id': 'news_rag_group_concho', # Đổi tên group ở đây
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(conf)
consumer.subscribe(['news_raw'])


def start_processing():
    print(" [Consumer] Đang chạy pipeline PostgreSQL-only...")

    pg_conn = get_postgres_conn()
    pg_conn.autocommit = False  # kiểm soát transaction

    try:
        while True:
            print(" [Consumer] Đang chờ message mới..." )
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                print(f"[ERROR] Kafka: {msg.error()}")
                continue

            try:
                data = json.loads(msg.value().decode('utf-8'))
                url = data.get('url', '')
                title = data.get('title', 'No Title')

                # Add author and publish date if available
                author = data.get('author', 'Unknown')
                publish_date = data.get('publish_date', None)

                if not url:
                    continue

                # Hash URL
                url_hash = hashlib.sha256(url.encode()).hexdigest()

                with pg_conn.cursor() as cursor:

                    # INSERT với ON CONFLICT (dedup cực sạch)
                    cursor.execute("""
                        INSERT INTO article_metadata (url_hash, url, title, content, author, publish_date)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url_hash) DO NOTHING
                        RETURNING url_hash;
                    """, (url_hash, url, title, json.dumps(data), author, publish_date))

                    result = cursor.fetchone()

                    if result:
                        pg_conn.commit()
                        print(f" [SUCCESS] Insert: {title[:50]}...")
                    else:
                        pg_conn.rollback()
                        print(f" [SKIP] Duplicate: {title[:50]}...")

            except Exception as e:
                pg_conn.rollback()
                print(f"[ERROR] Processing: {e}")
                pg_conn.close()

    except KeyboardInterrupt:
        print("\n [Consumer] Đang dừng...")
    finally:
        consumer.close()
        pg_conn.close()


if __name__ == "__main__":
    start_processing()