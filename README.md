# News RAG (Crawler + Kafka + PostgreSQL)

## Tổng quan dự án
News RAG là hệ thống thu thập tin tức tự động, đẩy dữ liệu thô vào Kafka và lưu metadata bài viết vào PostgreSQL.
Hệ thống gồm: Scrapy spider, pipeline Kafka, consumer PostgreSQL, Docker Compose.

##  Mục tiêu
- Cào tin tức từ các trang được cấu hình
- Gửi JSON bài viết vào topic Kafka `news_raw`
- Consumer đọc Kafka, dedup theo URL hash và insert vào bảng PostgreSQL `article_metadata`
- Xây dựng Data Warehouse dạng star schema để lưu trữ dữ liệu.
- Chia nội dung bài báo thành nhiều đoạn nhỏ phục vụ cho training mô hình sau này.

##  Thành phần chính
- `main.py`: Chạy 2 process (spider + consumer) với `multiprocessing`
- `crawler/spiders/spider.py`: Spider cào link và trích nội dung bài với `newspaper`
- `crawler/pipelines.py`: pipeline gửi item đến Kafka
- `consumer/consumer.py`: consumer đọc Kafka và lưu vào PostgreSQL
- `crawler/settings.py`: cài đặt Scrapy (pipeline, user-agent...)
- `crawler/spiders/config_site.json`: danh sách start URLs
- `docker-compose.yml`: Kafka, MongoDB, PostgreSQL
- `warehouse.sql`: xây dựng star schema để lưu trữ dữ liệu 
- `elt_warehouse.py`: Thu thập, Chuẩn hóa (Làm sạch và chia chunk), Nạp vào star schema 
- `vectorize.py`: Lấy chunks từ Data Warehouse, dùng mô hình AI (`BAAI/bge-m3`) chuyển thành Vector và đẩy lên Qdrant kèm Payload.
- `test_search.py`: Script mô phỏng truy vấn, kiểm thử khả năng tìm kiếm ngữ nghĩa của hệ thống.
- `reset_qdrant.py`: Tiện ích dọn dẹp nhanh bộ nhớ Vector DB.

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
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "CREATE TABLE IF NOT EXISTS article_metadata (url_hash text PRIMARY KEY, url text, title text, content jsonb, author text, publish_date text);"
```

### 4) Chạy pipeline
```bash
python main.py
```

### 5) Kiểm tra dữ liệu PostgreSQL
```bash
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "SELECT url, title FROM article_metadata LIMIT 5;" 
```

### 6) ETL dữ liệu nạp vào schema
```bash
python etl_warehouse.py
```

### 7) Kiểm tra dữ liệu trong schema
```bash
#kiểm tra bài báo & tác giả 
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "SELECT f.title, STRING_AGG(a.author_name, ' & ') as authors FROM fact_articles f JOIN fact_article_authors faa ON f.article_id = faa.article_id JOIN dim_author a ON faa.author_id = a.author_id GROUP BY f.article_id, f.title LIMIT 20;"
#kiểm tra danh sách chunk của bài báo đầu
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "SELECT chunk_index, LEFT(content, 800) FROM fact_chunks WHERE article_id = (SELECT MIN(article_id) FROM fact_articles) ORDER BY chunk_index;"
# Kiểm tra khối lượng và chất lượng chunks
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "SELECT (SELECT COUNT(*) FROM fact_articles) AS bai_bao_da_xu_ly, (SELECT COUNT(*) FROM fact_chunks) AS tong_so_chunks, ROUND((SELECT COUNT(*) FROM fact_chunks)::numeric / (SELECT COUNT(*) FROM fact_articles), 2) AS chunks_trung_binh;"
# Kiểm tra time của articles
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "SELECT year, month, COUNT(*) FROM dim_time JOIN fact_articles ON dim_time.time_id = fact_articles.time_id GROUP BY year, month ORDER BY year DESC;"
# reset kho dữ liệu
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "TRUNCATE TABLE article_metadata, dim_source, dim_time, dim_author, dim_content, fact_articles, fact_article_authors, fact_chunks RESTART IDENTITY CASCADE;"
# Kiểm tra đường link của các bên bị lỗi ngày
docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "SELECT title, url FROM article_metadata WHERE publish_date = 'Unknown' LIMIT 10;"
#vâng vâng mây mây...
```

### 8) Nhúng Vector và đẩy lên Qdrant (Vectorize)
```bash
make vectorize
```

### 9) Kiểm thử tìm kiếm ngữ nghĩa (Mô phỏng RAG)
```bash
python test_search.py
```


##  Cấu hình trang cào
Mở `crawler/spiders/config_site.json` và sửa danh sách URL (JSON array):
```json
["https://vnexpress.net/", "https://dantri.com.vn/", "https://vietnamnet.vn/"]
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