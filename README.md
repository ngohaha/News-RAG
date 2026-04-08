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
make reset #Để reset docker
```

### 3) Tạo bảng PostgreSQL (chỉ lần đầu)
```bash
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "CREATE TABLE IF NOT EXISTS article_metadata (url_hash text PRIMARY KEY, url text, title text, content jsonb, author text, publish_date text);"
```

### 4) Chạy pipeline
```bash
make main
```

### 5) Kiểm tra dữ liệu PostgreSQL
```bash
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "SELECT url, title FROM article_metadata LIMIT 5;" 
```

### 6) ETL dữ liệu nạp vào schema
```bash
make etl
```

### 7) Kiểm tra dữ liệu trong schema
```bash
#kiểm tra bài báo & tác giả 
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "SELECT f.title, STRING_AGG(a.author_name, ' & ') as authors FROM fact_articles f JOIN fact_article_authors faa ON f.article_id = faa.article_id JOIN dim_author a ON faa.author_id = a.author_id GROUP BY f.article_id, f.title LIMIT 20;"
#kiểm tra danh sách chunk của bài báo đầu
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "SELECT chunk_index, LEFT(content, 800) FROM fact_chunks WHERE article_id = (SELECT MIN(article_id) FROM fact_articles) ORDER BY chunk_index;"
# Kiểm tra khối lượng và chất lượng chunks
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "SELECT (SELECT COUNT(*) FROM fact_articles) AS bai_bao_da_xu_ly, (SELECT COUNT(*) FROM fact_chunks) AS tong_so_chunks, ROUND((SELECT COUNT(*) FROM fact_chunks)::numeric / (SELECT COUNT(*) FROM fact_articles), 2) AS chunks_trung_binh;"
# Kiểm tra time của articles
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "SELECT year, month, COUNT(*) FROM dim_time JOIN fact_articles ON dim_time.time_id = fact_articles.time_id GROUP BY year, month ORDER BY year DESC;"
# reset kho dữ liệu
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "TRUNCATE TABLE article_metadata, dim_source, dim_time, dim_author, dim_content, fact_articles, fact_article_authors, fact_chunks RESTART IDENTITY CASCADE;"
# Kiểm tra đường link của các bên bị lỗi ngày
docker exec -it postgres_news_rag psql -U newsrag -d news_rag -c "SELECT title, url FROM article_metadata WHERE publish_date = 'Unknown' LIMIT 10;"
#vâng vâng mây mây...
```

### 8) Nhúng Vector và đẩy lên Qdrant (Vectorize)
```bash
make vectorize
```

### 9) Kiểm thử tìm kiếm ngữ nghĩa (Mô phỏng RAG)
```bash
python vectorize/test_search.py
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