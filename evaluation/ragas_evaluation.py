import os
import sys # Import thêm sys để xử lý đường dẫn
import warnings # Import thêm thư viện chặn cảnh báo
import pandas as pd
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate

warnings.filterwarnings("ignore", category=DeprecationWarning)

from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)

from search.engine import Pipeline
from search.generator import generator_registry

def run_ragas_evaluation():
    load_dotenv()
    
    if not os.getenv("JUDGE_API_KEY"):
        print("[!] Thiếu JUDGE_API_KEY trong .env.")
        return

    # --- 1. KHỞI TẠO GIÁM KHẢO (GPT-4o-mini) ---
    print("[*] Đang mời Giám khảo GPT-4o-mini vào vị trí...")
    judge_key = os.getenv("JUDGE_API_KEY")
    
    # Truyền trực tiếp key vào mô hình
    judge_llm = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0.0, 
        api_key=judge_key,
        max_retries=5,         
        timeout=60           
    )
    judge_embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small", 
        api_key=judge_key,
        max_retries=5        
    )

    faithfulness.llm = judge_llm
    answer_relevancy.llm = judge_llm
    answer_relevancy.embeddings = judge_embeddings
    context_precision.llm = judge_llm
    context_recall.llm = judge_llm

    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

    # --- 2. ĐỌC BỘ ĐỀ THI TỰ VIẾT TỪ CSV ---
    testset_path = "evaluation/testset.csv"
    if not os.path.exists(testset_path):
        print(f"[!] Không tìm thấy file {testset_path}.")
        print("Hãy tạo file CSV gồm 2 cột: 'question' và 'ground_truth'")
        return

    print(f"[*] Đang đọc bộ đề thi từ {testset_path}...")
    df_testset = pd.read_csv(testset_path)
    test_cases = df_testset[['question', 'ground_truth']].to_dict('records')

    # --- 3. LẤY DANH SÁCH GENERATORS ĐỂ TEST ---
    available_models = generator_registry.list_generators()
    if not available_models:
        print("[!] Không có model nào được nạp từ Registry. Hãy kiểm tra lại file .env")
        return

    model_names = [m["name"] for m in available_models]
    print(f"[*] Đã tìm thấy {len(model_names)} models cần đánh giá: {model_names}")
    
    pipeline = Pipeline()

    # --- 4. CHẠY VÒNG LẶP ĐÁNH GIÁ TỪNG MODEL ---
    for model_name in model_names:
        print("\n" + "="*60)
        print(f"BẮT ĐẦU KIỂM TRA MÔ HÌNH: {model_name.upper()}")
        print("="*60)

        data_for_ragas = {
            "question": [],
            "answer": [],
            "contexts": [],
            "ground_truth": []
        }

        print(f"[*] {model_name} đang làm bài thi...")
        for idx, tc in enumerate(test_cases):
            question = str(tc["question"]).strip()
            print(f"  [{idx+1}/{len(test_cases)}] Đang trả lời: {question[:50]}...")
            
            # ĐIỂM CỐT LÕI: Truyền model_name vào hàm ask để ép pipeline dùng đúng model
            response = pipeline.ask(query=question, model=model_name)
            
            contexts = [hit.content for hit in response.results]
            answer = response.summary if response.summary else "Không có thông tin."
            
            data_for_ragas["question"].append(question)
            data_for_ragas["answer"].append(answer)
            data_for_ragas["contexts"].append(contexts)
            data_for_ragas["ground_truth"].append(str(tc["ground_truth"]).strip())

        dataset = Dataset.from_dict(data_for_ragas)

        print(f"\n[*] Giám khảo đang chấm điểm cho {model_name} (Vui lòng đợi)...")
        # raise_exceptions=False giúp script không bị chết nếu một model nào đó trả về câu trả lời bị lỗi
        evaluation_result = evaluate(dataset=dataset, metrics=metrics, raise_exceptions=False)

        print("\n" + "-"*50)
        print(f"BẢNG ĐIỂM CỦA: {model_name.upper()}")
        print("-"*50)
        print(evaluation_result)
        
        # --- 5. LƯU BẢNG ĐIỂM THEO TÊN MODEL ---
        df_result = evaluation_result.to_pandas()
        
        # Tạo tên file động chứa tên của model hiện tại
        output_path = f"evaluation/result/ragas_final_scores_{model_name}.csv"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df_result.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"[+] Đã lưu bảng điểm chi tiết tại: {output_path}")

    print("\nĐÃ HOÀN TẤT KIỂM TRA VÀ CHẤM ĐIỂM TOÀN BỘ HỆ THỐNG!")

if __name__ == "__main__":
    run_ragas_evaluation()