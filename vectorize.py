import psycopg2
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# --- 1. CẤU HÌNH KẾT NỐI ---
PG_CONFIG = {
    "dbname": "news_rag",
    "user": "tuan",
    "password": "tuan",
    "host": "localhost",
    "port": 5432
}

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "news_chunks"

def run_vectorization():
    print("[*] Đang tải mô hình BAAI/bge-m3...")
    model = SentenceTransformer('BAAI/bge-m3')
    
    # Kết nối Qdrant
    qdrant = QdrantClient(url=QDRANT_URL)
    
    # Tạo Collection trong Qdrant nếu chưa có
    if not qdrant.collection_exists(COLLECTION_NAME):
        print(f"[*] Đang tạo collection '{COLLECTION_NAME}' trong Qdrant...")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
    else:
        print(f"[*] Collection '{COLLECTION_NAME}' đã tồn tại.")

    try:
        # Kết nối Postgres để lấy dữ liệu
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()

        print("[*] Đang truy xuất chunks từ PostgreSQL Data Warehouse...")
        query = """
            SELECT c.article_id, c.chunk_index, c.content, a.title, m.url 
            FROM fact_chunks c 
            JOIN fact_articles a ON c.article_id = a.article_id
            JOIN article_metadata m ON a.url_hash = m.url_hash
        """
        cur.execute(query)
        chunks_data = cur.fetchall()

        if not chunks_data:
            print("[!] Không có chunk nào để xử lý.")
            return

        # Tính tổng số chunks để theo dõi tiến độ
        total_chunks = len(chunks_data)
        print(f"[*] Bắt đầu Vector hóa và đẩy {total_chunks} chunks lên Qdrant...")

        points = []
        # Qdrant yêu cầu ID phải là số nguyên (integer) hoặc UUID duy nhất cho mỗi vector.
        # Tạo một ID duy nhất bằng cách kết hợp article_id và chunk_index
        for idx, row in enumerate(chunks_data):
            article_id, chunk_index, content, title, url = row
            
            # Vectorize content
            vector = model.encode(content).tolist()
            
            # Tạo Point (Vector + Payload) cho Qdrant
            point = PointStruct(
                id=idx + 1, # ID tăng dần
                vector=vector,
                payload={
                    "article_id": article_id,
                    "chunk_index": chunk_index,
                    "title": title,
                    "url": url,
                    "content": content
                }
            )
            points.append(point)
            
            # Đẩy dữ liệu theo batch (100 record một lần)
            if len(points) >= 100:
                qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
                points = []
                print(f"  [+] Đã đẩy {idx + 1}/{total_chunks} chunks lên Qdrant...")

        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"  [+] Đã đẩy {total_chunks}/{total_chunks} chunks lên Qdrant...")

        print("\n[SUCCESS] Đã hoàn thành nạp dữ liệu vào Qdrant Vector DB!")

    except Exception as e:
        print(f"[ERROR] Quá trình thất bại: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

if __name__ == "__main__":
    run_vectorization()