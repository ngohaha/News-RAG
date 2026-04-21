.PHONY: help install test test-cov clean

# --- BIẾN ---
PYTHON = venv/bin/python
SCRAPY = venv/bin/scrapy
DOCKER_COMPOSE = docker-compose
PYTEST = pytest

# --- LỆNH CHÍNH ---

.PHONY: all setup up down restart crawl consume status clean main etl vectorize reset_qdrant db-count kafka-peek

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

main:
	$(PYTHON) main.py

etl:
	$(PYTHON) etl/etl_warehouse.py

vectorize:
	$(PYTHON) vectorize/vectorize.py

reset_qdrant:
	$(PYTHON) vectorize/reset_qdrant.py

# Tiện ích
db-count:
	@echo "[DATABASE] Số lượng bài báo trong PostgreSQL (AWS RDS):"
	@docker run --rm -e PGPASSWORD=tuantran postgres:latest psql -h news-rag-cloud.cl2emq8kis9l.ap-southeast-2.rds.amazonaws.com -U tuantran -d postgres -c "SELECT count(*) FROM article_metadata;"
	@echo "[DATABASE] Số lượng bài báo trong MongoDB:"
	@docker exec -it mongo_news_rag mongosh -u newsrag -p newsrag --authenticationDatabase admin news_db --eval "db.articles.countDocuments()"
	
kafka-peek:
	@echo "[KAFKA] Xem log Kafka để debug nhanh:"
	docker exec -it kafka_news_rag /opt/kafka/bin/kafka-console-consumer.sh --topic news_raw --bootstrap-server localhost:9092 --from-beginning --max-messages 5

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "[CLEAN] Đã dọn dẹp file rác."

test-gen:
	@echo "[*] Đang kiểm tra Generator API..."
	PYTHONPATH=. $(PYTHON) -m tests.search.test_generator

test-pipeline:
	@echo "[*] Đang kiểm tra Pipeline API..."
	PYTHONPATH=. $(PYTHON) -m tests.search.test_pipeline

test-interactive:
	@echo "[*] Đang kiểm tra..."
	PYTHONPATH=. $(PYTHON) -m tests.search.test_interactive



