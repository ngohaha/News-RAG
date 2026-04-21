import logging
from dotenv import load_dotenv
from search.engine import Pipeline
from search.generator import generator_registry

# Tắt bớt log rác để terminal sạch sẽ
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def interactive_test():
    load_dotenv()
    
    print("="*50)
    print("NEWS-RAG INTERACTIVE TEST")
    print("="*50)

    # 1. Khởi tạo Pipeline
    pipeline = Pipeline()
    
    # 2. Hiển thị danh sách model đang có
    available_models = generator_registry.list_generators()
    if not available_models:
        print("[!] Không tìm thấy model nào trong registry. Kiểm tra .env!")
        return

    print("\nCác model sẵn sàng:")
    for i, model_info in enumerate(available_models, 1):
        print(f"{i}. {model_info['name']} [{model_info['provider'].upper()}] - ID: {model_info['model_id']}")
    
    # 3. Chọn model để test
    choice = input("\nNhập tên model muốn dùng (nhấn Enter để lấy mặc định): ").strip()
    selected_model = choice if choice else "default"

    print(f"\n✅ Đang sử dụng model: {selected_model}")
    print("--- Nhập 'exit' hoặc 'quit' để thoát ---")
    print("--- Nhập 'switch' để đổi model ---\n")

    while True:
        try:
            # Nhập câu hỏi từ bàn phím
            query = input("Đặt câu hỏi: ").strip()

            if query.lower() in ['exit', 'quit']:
                print("Tạm biệt!")
                break
            
            if query.lower() == 'switch':
                print("\nCác model sẵn sàng:")
                for i, model_info in enumerate(available_models, 1):
                    print(f"{i}. {model_info['name']} [{model_info['provider'].upper()}] - ID: {model_info['model_id']}")
                choice = input("Nhập tên model mới: ").strip()
                selected_model = choice if choice else "default"
                print(f"Đã chuyển sang: {selected_model}\n")
                continue

            if not query:
                continue

            print("AI đang suy nghĩ...")
            
            # 4. Chạy Pipeline
            response= pipeline.ask(query, model=selected_model)

            # 5. Hiển thị kết quả
            print("\n" + "-"*30)
            if response:
                print(f" AI trả lời:\n{response.summary}")
                print(f"\nThông tin: {response.total} nguồn tin | Thời gian: {response.duration_ms}ms")
                if response.results:
                    print("\nReferences Used:")
                    for i, hit in enumerate(response.results):
                        print(f"   [{i+1}] {hit.title} | Link: {hit.url}")
            else:
                print("AI không tìm thấy câu trả lời phù hợp.")
            print("-"*30 + "\n")

        except KeyboardInterrupt:
            print("\nĐã dừng chương trình.")
            break
        except Exception as e:
            print(f"Có lỗi xảy ra: {e}\n")

if __name__ == "__main__":
    interactive_test()