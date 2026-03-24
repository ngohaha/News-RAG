# --- BIẾN ---
PYTHON = venv/bin/python
SCRAPY = venv/bin/scrapy
DOCKER_COMPOSE = docker compose

# --- LỆNH CHÍNH ---

.PHONY: all setup up down restart crawl consume status clean

# Khởi tạo môi trường lần đầu
setup:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt
	@echo "[EVIROMENT SETUP] Đã tạo môi trường ảo và cài đặt dependencies."

venv:
	if [ ! -d "venv" ]; then \
		$(MAKE) setup; \
	else \
		@echo "[ENVIRONMENT] Môi trường ảo đã tồn tại. Sử dụng 'source venv/bin/activate' để kích hoạt."; \
	fi
	source venv/bin/activate
	@echo "[ENVIRONMENT] Đã kích hoạt môi trường ảo. Sử dụng 'source venv/bin/activate' để kích hoạt."

# Quản lý Docker
up:
	$(DOCKER_COMPOSE) up -d
	@echo "[DOCKER] Đã bật Postgres, MongoDB và Kafka."

down:
	$(DOCKER_COMPOSE) down
	@echo "[DOCKER] Đã dừng và xóa các container."

restart: down up

# Vận hành hệ thống
crawl:
	export PYTHONPATH=. && $(SCRAPY) crawl news_rag_spider

consume:
	$(PYTHON) consumer/consumer.py

# Tiện ích
db-count:
	@echo "[DATABASE] Số lượng bài báo trong PostgreSQL:"
	@docker exec -it postgres_news_rag psql -U tuan -d news_rag -c "SELECT count(*) FROM article_metadata;"
	@echo "[DATABASE] Số lượng bài báo trong MongoDB:"
	@docker exec -it mongo_news_rag mongosh -u tuan -p tuan --authenticationDatabase admin news_db --eval "db.articles.countDocuments()"

kafka-peek:
	@echo "[KAFKA] Xem log Kafka để debug nhanh:"
	docker exec -it kafka_news_rag /opt/kafka/bin/kafka-console-consumer.sh --topic news_raw --bootstrap-server localhost:9092 --from-beginning --max-messages 5

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "[CLEAN] Đã dọn dẹp file rác."