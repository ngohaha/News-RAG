from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333")
client.delete_collection("news_chunks")
print("[OK] Đã xóa bộ nhớ Qdrant cũ thành công!")