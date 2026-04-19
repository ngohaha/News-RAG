import psycopg2
import uuid
from FlagEmbedding import BGEM3FlagModel 
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, SparseVectorParams, SparseVector

# --- 1. CẤU HÌNH KẾT NỐI ---
PG_CONFIG = {
    "dbname": "postgres",
    "user": "tuantran",
    "password": "tuantran",
    "host": "news-rag-cloud.cl2emq8kis9l.ap-southeast-2.rds.amazonaws.com"
}

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "news_chunks" 

def generate_uuid(article_id, chunk_index):
    """Tạo một UUID cố định vĩnh viễn dựa trên article_id và chunk_index"""
    unique_string = f"article_{article_id}_chunk_{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))

def run_vectorization():
    print("[*] Đang tải mô hình BAAI/bge-m3 (Phiên bản Hybrid)...")
    model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True) 
    
    qdrant = QdrantClient(url=QDRANT_URL)
    
    # Cấu hình Qdrant nhận 2 Vector cùng lúc (Dense & Sparse)
    if not qdrant.collection_exists(COLLECTION_NAME):
        print(f"[*] Đang tạo collection Hybrid '{COLLECTION_NAME}' trong Qdrant...")
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": VectorParams(size=1024, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams()
            }
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
        
        # Lọc Incremental Load bằng UUID
        for row in all_chunks:
            article_id, chunk_index, content, title, url = row
            point_id = generate_uuid(article_id, chunk_index)
            
            try:
                result = qdrant.retrieve(collection_name=COLLECTION_NAME, ids=[point_id])
                if not result:
                    chunks_to_process.append((point_id, article_id, chunk_index, content, title, url))
            except Exception:
                chunks_to_process.append((point_id, article_id, chunk_index, content, title, url))

        total_new_chunks = len(chunks_to_process)
        if total_new_chunks == 0:
            print("[SUCCESS] Dữ liệu Hybrid trên Qdrant đã Up-to-date!")
            return

        print(f"[*] Bắt đầu Vector hóa Hybrid và đẩy {total_new_chunks} chunks MỚI lên Qdrant...")

        points = []
        for idx, row in enumerate(chunks_to_process):
            point_id, article_id, chunk_index, content, title, url = row
            
            # Yêu cầu model sinh ra cả 2 loại vector
            output = model.encode([content], return_dense=True, return_sparse=True)
            
            # 1. Bóc tách Vector Ngữ nghĩa (Dense - 1024 chiều)
            dense_vec = output['dense_vecs'][0].tolist()
            
            # 2. Bóc tách Vector Từ khóa (Sparse - Trọng số BM25)
            lexical_dict = output['lexical_weights'][0]
            
            # Lọc ID trùng lặp và giữ trọng số lớn nhất (Max pooling)
            sparse_dict = {}
            for token_str, weight in lexical_dict.items():
                token_id = model.tokenizer.convert_tokens_to_ids(token_str)
                
                # Tránh trường hợp Tokenizer trả về mảng rỗng hoặc list
                if isinstance(token_id, list):
                    if not token_id: continue
                    token_id = token_id[0]
                
                # Ép kiểu rõ ràng để Qdrant không báo lỗi JSON
                token_id = int(token_id)
                weight = float(weight)
                
                if token_id in sparse_dict:
                    sparse_dict[token_id] = max(sparse_dict[token_id], weight)
                else:
                    sparse_dict[token_id] = weight
            
            token_ids = list(sparse_dict.keys())
            weights = list(sparse_dict.values())
            
            # 3. Tạo Point để đẩy lên Qdrant
            point = PointStruct(
                id=point_id, 
                vector={
                    "dense": dense_vec,
                    "sparse": SparseVector(indices=token_ids, values=weights)
                },
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

        print("\n[SUCCESS] Đã nạp thành công dữ liệu HYBRID vào Qdrant Vector DB!")

    except Exception as e:
        print(f"[ERROR] Quá trình thất bại: {e}")
    finally:
        if cur: cur.close()
        if conn: conn.close()

if __name__ == "__main__":
    run_vectorization()