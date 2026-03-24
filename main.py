import multiprocessing
import consumer.consumer as consumer_module
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from crawler.spiders.spider import NewsRAGSpider
import time

def run_spider():
    # Khởi tạo lại settings bên trong process con để tránh share memory lỗi
    settings = get_project_settings()
    process = CrawlerProcess(settings)
    process.crawl(NewsRAGSpider)
    process.start()

def run_consumer():
    # Đảm bảo Consumer có thời gian khởi tạo kết nối DB sạch
    time.sleep(2) 
    consumer_module.start_processing()


if __name__ == "__main__":
    # Ép dùng phương thức 'spawn' để tạo process sạch hoàn toàn (giống Windows/macOS)
    # Điều này cực kỳ quan trọng trên Arch để tránh lỗi share signal
    multiprocessing.set_start_method('spawn', force=True)

    p_consumer = multiprocessing.Process(target=run_consumer)
    p_spider = multiprocessing.Process(target=run_spider)

    try:
        p_consumer.start()
        print("Consumer đã sẵn sàng...")
        
        time.sleep(3) # Đợi Consumer ổn định Group ID với Kafka
        
        p_spider.start()
        print("Spider bắt đầu cào...")

        p_spider.join()
        time.sleep(50) # Đợi Consumer xử lý nốt các message còn lại sau khi Spider xong

        # Lưu ý: Consumer thường chạy vô tận, nếu muốn dừng khi spider xong:
        p_consumer.terminate() 
        p_consumer.join()

        
    except KeyboardInterrupt:
        print("\n Đang dừng hệ thống...")
        p_spider.terminate()
        p_consumer.terminate()