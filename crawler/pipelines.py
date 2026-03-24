import json
from confluent_kafka import Producer

class KafkaPipeline:
    def __init__(self):
        # Lưu ý: Nếu chạy từ ngoài Docker, dùng localhost:9092
        self.producer = Producer({'bootstrap.servers': 'localhost:9092'})

    def process_item(self, item, spider):
        line = json.dumps(dict(item), ensure_ascii=False).encode('utf-8')
        self.producer.produce('news_raw', value=line)
        self.producer.flush() # <--- CỰC KỲ QUAN TRỌNG
        return item