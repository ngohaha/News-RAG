# News RAG (Crawler + Kafka + PostgreSQL + Qdrant)

## Tổng quan dự án
News RAG là hệ thống Data Pipeline end-to-end: tự động thu thập tin tức, xử lý luồng dữ liệu thời gian thực (Streaming) qua Kafka, chuẩn hóa vào Data Warehouse (PostgreSQL) và nhúng (Embedding) thành Vector đưa lên Qdrant.
Dự án cung cấp nền tảng backend vững chắc để xây dựng các ứng dụng Chatbot AI (Retrieval-Augmented Generation - RAG) có khả năng trả lời câu hỏi dựa trên tin tức thực tế.

## Mục tiêu
- **Cào tin tức tự động** từ các trang báo điện tử lớn (VnExpress, Dân Trí, VietnamNet).
- **Streaming:** Đẩy JSON bài viết vào topic Kafka `news_raw` để đảm bảo luồng dữ liệu không bị thất thoát.
- **Consuming & Dedup:** Đọc dữ liệu từ Kafka, loại bỏ trùng lặp bằng URL Hash và nạp vào bảng PostgreSQL `article_metadata`.
- **ETL & Data Warehouse:** Làm sạch HTML, chia nhỏ nội dung (Chunking) và lưu trữ theo chuẩn mô hình sao (Star Schema).
- **Vector DB:** Nhúng (Vectorize) các chunks dữ liệu bằng mô hình `BAAI/bge-m3` và lưu trữ trên Qdrant để phục vụ tìm kiếm ngữ nghĩa.

## Cấu trúc thư mục
Dự án được thiết kế theo module hóa chuẩn Data Engineering:
```text
NEWS-RAG/
├── app/                    # Chứa ứng dụng giao diện (Streamlit/FastAPI)
│   └── dashboard.py
├── config/                 # Cấu hình tập trung (config_site.json)
│   └── config_site.json    
├── consumer/               # Pipeline xử lý dữ liệu Kafka sang DB thô
│   └── consumer.py
├── crawler/                # Lõi Scrapy (Spiders, Pipelines, Settings)
│   ├── spiders/
│   │   ├── __init__.py     
│   │   └── spider.py       # Spider cào link và trích nội dung bài với `newspaper`
│   ├── __init__.py
│   ├── pipelines.py
│   └── settings.py
├── database/               # Script khởi tạo cấu trúc Data Warehouse (warehouse.sql)
│   └── warehouse.sql       
├── etl/                    # Tiến trình Transform & Load (etl_warehouse.py)
│   └── etl_warehouse.py    
├── vectorize/              # Xử lý nhúng AI và giao tiếp với Qdrant Vector DB
│   ├── reset_qdrant.py
│   ├── test_search.py
│   └── vectorize.py
│──  search/
│  ├── __init__.py          # Khởi tạo module, export các class chính (Pipeline, generator_registry)
│  ├── config.py            # Quản lý cấu hình LLM, API Key, Scaling (Pydantic Settings)
│  ├── engine.py            # Chứa class Pipeline - Điều phối luồng (Retriever -> Generator)
│  ├── generator.py         # Lõi Generator: Registry, Singleton, Base Classes cho các AI Model
│  ├── retriever.py         # Logic kết nối Qdrant, thực hiện Vector Search để lấy Context
│  ├── prompts.py           # Quản lý các System Prompt mẫu để tối ưu câu trả lời tiếng Việt
│  ├── schemas.py           # Định nghĩa cấu hình dữ liệu (Pydantic Models: SearchHit, GeneratorResponse)
│  ├── logger_setup.py      # Cấu hình logging tập trung (Log ra console và file app.log)
│  ├── utils.py             # Các hàm bổ trợ (xử lý chuỗi, tính thời gian, format văn bản)
│  └── app.log              # File lưu trữ vết (logs) của hệ thống khi vận hành         
├── .gitignore
├── docker-compose.yml
├── main.py                 # File khởi chạy Orchestrator 
├── Makefile                # Bộ lệnh tự động hóa vận hành hệ thống
├── README.md               
├── requirements.txt        
└── scrapy.cfg
```

##  Chuẩn bị & chạy
### 1) Cài dependencies Python
```bash
make setup
```

### 2) Khởi động Docker Compose
```bash
make up
make down #Nếu muốn tắt
make restart #Để reset docker
```

### 3) Tạo bảng PostgreSQL (không cần nữa nhưng mà t lười xóa ai rảnh thì xóa hộ với)
```bash
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "CREATE TABLE IF NOT EXISTS article_metadata (url_hash text PRIMARY KEY, url text, title text, content jsonb, author text, publish_date text);"
```

### 4) Chạy pipeline
```bash
make main
```
với
### 5) Kiểm tra dữ liệu PostgreSQL
```bash
python init_db/test_db.py" 
```

### 6) ETL dữ liệu nạp vào schema
```bash
make etl
```

### 7) Kiểm tra dữ liệu trong schema
```bash
streamlit run app/dashboard.py
```

### 8) Nhúng Vector và đẩy lên Qdrant (Vectorize)
```bash
make vectorize
```

```
## Lệnh kiểm tra & Tiện ích (Makefile & SQL)
```bash
# Xem tổng số bài báo hiện có trong Database thô
make db-count

# Xem nhanh 5 tin đang chạy trong Kafka
make kafka-peek

# Dọn dẹp các file rác (cache) sinh ra trong quá trình chạy code
make clean

# Xóa sạch bộ nhớ Vector DB trên Qdrant
make reset_qdrant
```
### 9) Search & RAG (Hệ thống truy vấn AI)
Đây là tầng ứng dụng cuối cùng, cho phép người dùng hỏi đáp dựa trên toàn bộ dữ liệu tin tức đã được nhúng (vectorize). Hệ thống hỗ trợ Scaling LLM - cho phép chạy song song nhiều mô hình khác nhau để so sánh kết quả.
**Tính năng chính:**
***Multi-Model Support:*** Tích hợp linh hoạt Groq (Qwen, Llama), Google Gemini, OpenAI và Ollama (Local).
***Generator Registry:*** Quản lý tập trung các instance model thông qua Pattern Singleton và Registry.
***Scaling:*** Thay đổi số lượng và loại model chỉ bằng cách chỉnh sửa file .env mà không cần sửa code.
**Quy trình:**
1. Query Processing: Nhận câu hỏi từ người dùng thông qua Pipeline.
2. Retrieval: Retriever thực hiện tìm kiếm ngữ nghĩa trên Qdrant để lấy ra Top-K đoạn tin tức liên quan nhất.
3. Augmentation: Toàn bộ ngữ cảnh (Context) được format và đưa vào Prompt chuyên dụng.
4. Generation: GeneratorRegistry điều phối model LLM được chọn để tổng hợp thông tin và trả lời người dùng bằng tiếng Việt.
| Lệnh | Mô tả |
| :--- | :--- |
| `make test-interative` | Khởi động giao diện chat tương tác CLI (nhập liệu từ bàn phím). |
| `make test-gen` | Kiểm tra riêng lẻ khả năng phản hồi của các Generator. |
| `make test-pipeline` | Chạy kiểm tra tích hợp toàn bộ luồng từ Retrieval đến Generation. |


##  Cấu hình trang cào
Mở `crawler/spiders/config_site.json` và sửa danh sách URL (JSON array):
```json
[
  "[https://vnexpress.net/](https://vnexpress.net/)", 
  "[https://dantri.com.vn/](https://dantri.com.vn/)", 
  "[https://vietnamnet.vn/](https://vietnamnet.vn/)"
]
```


##  Chi tiết luồng dữ liệu
1. Spider bắt đầu từ `config_site.json`.
2. Duyệt link: nếu link `.html` là bài viết thì gọi `parse_article`; nếu link chuyên mục thì tiếp tục parse.
3. `parse_article` dùng `newspaper.Article` parse nội dung, yield item gồm URL, tiêu đề, nội dung, tác giả, ngày xuất bản.
4. `KafkaPipeline` gửi item JSON vào topic `news_raw`.
5. `consumer` đọc topic, hash URL và insert vào `article_metadata` với `ON CONFLICT DO NOTHING` để tránh trùng.
6. `init_warehouse_schema` trong `etl_warehouse` đọc dữ liệu từ file sql để khởi tạo các bảng cần thiết.
7. `run_etl_warehouse` trong `etl_warehouse` khởi tạo ID = 0 cho author và publish_date 'Unknown', làm sạch dữ liệu, cắt chunk nội dung, nạp vào các bảng tương ứng.
8. Vectorizing: `vectorize.py` cho các chunks từ DB, chạy qua mô hình BAAI/bge-m3 để tạo mảng Vector 1024 chiều, gói cùng metadata (URL, Title, Content) thành Payload và upsert lên Qdrant.

##  Lưu ý quan trọng
- Nếu Kafka hoặc PostgreSQL không kết nối được, kiểm tra trạng thái container và cổng.
- `consumer/consumer.py` đang kết nối Kafka `localhost:9092` và PostgreSQL host `localhost`; chạy trên host hoặc container khác cần chỉnh lại.
- Spiders hiện chỉ parse `vnexpress.net` trong parse_article, nếu muốn mở rộng cần điều chỉnh logic lọc url.
- Nếu `main.py` không consumer được, thử đổi tên `group_id` trong  `consumer.py` sau đó khởi động lại. 
- Qdrant hoạt động trên cổng 6333 (REST) và 6334 (gRPC). Hãy chắc chắn các port này không bị xung đột trên máy host.
- Trong lần chạy make vectorize đầu tiên, hệ thống sẽ mất một chút thời gian để tải model BAAI/bge-m3 (khoảng vài GB) về máy.

##  Mở rộng
- Thêm cấu hình cho site khác (chỉ parse theo định dạng domain)
- Lưu đầy đủ metadata vào MongoDB hoặc vector DB cho RAG
- Thêm dockerfile/entrypoint để deploy app trong container

---