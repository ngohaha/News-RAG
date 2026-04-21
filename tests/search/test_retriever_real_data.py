import os
import logging
from anyio import Path
from dotenv import load_dotenv

# Import các thành phần core từ project của bạn
from search.retriever import Retriever

# Cấu hình log để theo dõi tiến trình load model và kết nối
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_real_search():
    # 1. Load biến môi trường từ file .env
    load_dotenv()
    
    print("\n" + "="*60)
    print("🚀 KHỞI CHẠY RETRIEVER VỚI DỮ LIỆU THẬT (QDRANT CLOUD)")
    print("="*60)

    # 4. Khởi tạo Retriever thật
    try:
        print("[*] Đang tải mô hình AI và kết nối Cloud... (Vui lòng đợi 10-20s)")
        # Lần gọi này sẽ kích hoạt download model thật từ HuggingFace nếu máy chưa có
        retriever = Retriever()
        print("[SUCCESS] Retriever đã sẵn sàng!")
    except Exception as e:
        print(f"[ERROR] Khởi tạo thất bại: {e}")
        return

    # 5. Thực hiện truy vấn thực tế
    # Bạn có thể thay đổi câu hỏi này để test các nội dung bạn đã nạp vào DB
    query = "Tình hình giá dầu mỏ thế giới hôm nay" 
    
    print(f"\n🔍 Truy vấn: '{query}'")
    print("-" * 60)

    try:
        results = retriever.search(query)

        if not results:
            print("⚠️ KHÔNG TÌM THẤY KẾT QUẢ.")
            print("Gợi ý: Kiểm tra lại collection name hoặc đảm bảo đã bật Hybrid Search.")
        else:
            print(f"✅ Tìm thấy {len(results)} kết quả (đã qua Reranking):\n")
            for i, hit in enumerate(results):
                print(f"Top {i+1} [Score: {hit.score:.4f}]")
                print(f"  📌 Tiêu đề: {hit.title}")
                print(f"  🔗 Link: {hit.url}")
                print(f"  📝 Nội dung: {hit.content[:250]}...")
                print("-" * 60)

    except Exception as e:
        print(f"[ERROR] Lỗi trong quá trình tìm kiếm: {e}")

if __name__ == "__main__":
    run_real_search()