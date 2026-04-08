import psycopg2
import uuid
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# --- 1. CẤU HÌNH KẾT NỐI ---
PG_CONFIG = {
    "dbname": "news_rag",
    "user": "newsrag",
    "password": "newsrag",
    "host": "localhost",
    "port": 5432
}

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "news_chunks"

def generate_uuid(article_id, chunk_index):
    """Tạo một UUID cố định vĩnh viễn dựa trên article_id và chunk_index"""
    unique_string = f"article_{article_id}_chunk_{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

def run_vectorization():
    print("[*] Đang tải mô hình BAAI/bge-m3...")
    model = SentenceTransformer('BAAI/bge-m3')
    
    qdrant = QdrantClient(url=QDRANT_URL)
    
    if not qdrant.collection_exists(COLLECTION_NAME):
        print(f"[*] Đang tạo collection '{COLLECTION_NAME}' trong Qdrant...")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
    else:
        print(f"[*] Collection '{COLLECTION_NAME}' đã tồn tại.")

    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur = conn.cursor()

        print("[*] Đang truy xuất toàn bộ chunks từ PostgreSQL...")
        query = """
            SELECT c.article_id, c.chunk_index, c.content, a.title, m.url 
            FROM fact_chunks c 
            JOIN fact_articles a ON c.article_id = a.article_id
            JOIN article_metadata m ON a.url_hash = m.url_hash
        """
        cur.execute(query)
        all_chunks = cur.fetchall()

        if not all_chunks:
            print("[!] Không có chunk nào trong Warehouse.")
            return

        print("[*] Đang đối chiếu với Qdrant để tìm các chunks mới...")
        chunks_to_process = []
        
        # Lọc ra những chunk chưa từng tồn tại trên Qdrant
        for row in all_chunks:
            article_id, chunk_index, content, title, url = row
            point_id = generate_uuid(article_id, chunk_index)
            
            # Kiểm tra xem ID này đã có trên Qdrant chưa
            try:
                # Nếu retrieve trả về danh sách rỗng -> ID này chưa có
                result = qdrant.retrieve(collection_name=COLLECTION_NAME, ids=[point_id])
                if not result:
                    chunks_to_process.append((point_id, article_id, chunk_index, content, title, url))
            except Exception:
                # Trường hợp lỗi kết nối nhẹ, an toàn nhất là cứ thêm vào danh sách xử lý
                chunks_to_process.append((point_id, article_id, chunk_index, content, title, url))

        total_new_chunks = len(chunks_to_process)
        if total_new_chunks == 0:
            print("[SUCCESS] Tất cả các chunks đã có sẵn trên Qdrant. Hệ thống Vector DB đã Up-to-date!")
            return

        print(f"[*] Bắt đầu Vector hóa và đẩy {total_new_chunks} chunks MỚI lên Qdrant...")

        points = []
        for idx, row in enumerate(chunks_to_process):
            point_id, article_id, chunk_index, content, title, url = row
            
            vector = model.encode(content).tolist()
            
            point = PointStruct(
                id=point_id, # Sử dụng UUID chuẩn xác định
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
            
            if len(points) >= 100:
                qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
                points = []
                print(f"  [+] Đã đẩy {idx + 1}/{total_new_chunks} chunks mới lên Qdrant...")

        if points:
            qdrant.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"  [+] Đã đẩy {total_new_chunks}/{total_new_chunks} chunks mới lên Qdrant...")

        print("\n[SUCCESS] Đã hoàn thành cập nhật dữ liệu vào Qdrant Vector DB!")

    except Exception as e:
        print(f"[ERROR] Quá trình thất bại: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

if __name__ == "__main__":
    run_vectorization()