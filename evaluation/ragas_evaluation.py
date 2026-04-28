import os
import pandas as pd
from dotenv import load_dotenv
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

# Import OpenAI từ Langchain để làm Giám khảo
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from search.engine import Pipeline

def run_ragas_evaluation():
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("[!] Thiếu OPENAI_API_KEY trong .env.")
        return

    # --- 1. KHỞI TẠO GIÁM KHẢO (GPT-4o-mini) ---
    print("[*] Đang mời Giám khảo GPT-4o-mini vào vị trí...")
    judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    judge_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    faithfulness.llm = judge_llm
    answer_relevancy.llm = judge_llm
    answer_relevancy.embeddings = judge_embeddings
    context_precision.llm = judge_llm
    context_recall.llm = judge_llm

    # --- 2. ĐỌC BỘ ĐỀ THI TỰ VIẾT TỪ CSV ---
    testset_path = "tests/evaluation/testset.csv"
    if not os.path.exists(testset_path):
        print(f"[!] Không tìm thấy file {testset_path}.")
        print("Hãy tạo file CSV gồm 2 cột: 'question' và 'ground_truth'")
        return

    print(f"[*] Đang đọc bộ đề thi từ {testset_path}...")
    df_testset = pd.read_csv(testset_path)
    test_cases = df_testset[['question', 'ground_truth']].to_dict('records')

    data_for_ragas = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": []
    }

    # --- 3. GỌI PIPELINE RAG ĐỂ LÀM BÀI ---
    print("[*] Hệ thống RAG đang làm bài thi...")
    pipeline = Pipeline()
    
    for idx, tc in enumerate(test_cases):
        question = str(tc["question"]).strip()
        print(f"  [{idx+1}/{len(test_cases)}] Đang trả lời: {question[:50]}...")
        
        response = pipeline.ask(query=question)
        
        contexts = [hit.content for hit in response.results]
        answer = response.summary if response.summary else "Không có thông tin."
        
        data_for_ragas["question"].append(question)
        data_for_ragas["answer"].append(answer)
        data_for_ragas["contexts"].append(contexts)
        data_for_ragas["ground_truth"].append(str(tc["ground_truth"]).strip())

    dataset = Dataset.from_dict(data_for_ragas)

    # --- 4. CHẤM ĐIỂM ---
    print("\n[*] Giám khảo đang chấm điểm (Vui lòng đợi vài phút)...")
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    
    evaluation_result = evaluate(dataset=dataset, metrics=metrics)

    print("\n" + "="*50)
    print("KẾT QUẢ ĐÁNH GIÁ RAGAS:")
    print("="*50)
    print(evaluation_result)
    
    df_result = evaluation_result.to_pandas()
    output_path = "tests/evaluation/ragas_final_scores.csv"
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_result.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n[+] Bảng điểm chi tiết lưu tại: {output_path}")

if _name_ == "_main_":
    run_ragas_evaluation()