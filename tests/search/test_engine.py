import sys
import os
from pprint import pprint

# Ensure the root directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from search.engine import Pipeline

def run_e2e_test():
    print("\n" + "="*60)
    print("🚀 STARTING FULL RAG PIPELINE TEST")
    print("="*60)

    try:
        # 1. Initialize Pipeline
        print("[*] Initializing Pipeline (Loading models and connecting to Cloud)...")
        pipeline = Pipeline()
        
        # 2. Define a query based on your oil price news data
        query = "Tình hình giá dầu thô Brent năm 2024 và 2026 thế nào?"
        print(f"\n[?] Câu hỏi: {query}")
        
        # 3. Execute the pipeline
        print("[*] Đang xử lý...")
        response = pipeline.ask(query=query, model="gemini-2.5-flash")

        # 4. Display Results
        print("\n" + "✨" + "-"*15 + " CÂU TRẢ LỜI " + "-"*15)
        if response.summary:
            print(f"{response.summary}")
        else:
            print("Không tìm thấy câu trả lời.")
        
        print("-" * 55)
        print(f"⏱️ Duration: {response.duration_ms} ms")
        print(f"📚 Sources Found: {response.total}")
        
        if response.results:
            print("\n🔗 References Used:")
            for i, hit in enumerate(response.results):
                print(f"   [{i+1}] {hit.title} | Link: {hit.url}")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    run_e2e_test()