from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

print("Đang tải model...")
model = SentenceTransformer('BAAI/bge-m3')
qdrant = QdrantClient(url="http://localhost:6333")

# Đặt câu hỏi liên quan đến tin tức vừa cào
query_text = "Giá vàng gần đây như thế nào?"
print(f"Câu hỏi: '{query_text}'")

# Vector hóa câu hỏi
query_vector = model.encode(query_text).tolist()

# Tìm kiếm 3 chunks giống nhất trong Qdrant
print("Đang tìm kiếm trong Qdrant...\n" + "-"*50)

search_results = qdrant.query_points(
    collection_name="news_chunks",
    query=query_vector,
    limit=3  
).points

for i, hit in enumerate(search_results):
    print(f"Top {i+1} | Độ tương đồng (Score): {hit.score:.4f}")
    print(f"Tiêu đề: {hit.payload['title']}")
    print(f"Nội dung: {hit.payload['content'][:200]}...") # In 200 ký tự đầu cho đỡ rối
    print(f"URL: {hit.payload['url']}\n")