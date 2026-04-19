from qdrant_client import QdrantClient
QDRANT_URL = "https://1dbe8b30-05be-452b-8ae6-bd3d0d18464c.us-west-2-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIiwic3ViamVjdCI6ImFwaS1rZXk6ZTY1YzEwZDMtYmRlZi00MjkzLTllNzgtNGI0ZThiOWRjNTMyIn0.PXfxHDR-w_64a_0HdP9Mw3KHZbGmC59F_DG4VJoCezE"
client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY
    )
client.delete_collection("news_chunks")
print("[OK] Đã xóa bộ nhớ Qdrant cũ thành công!")