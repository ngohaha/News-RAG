import os
import json
import multiprocessing
import time
import consumer.consumer as consumer_module
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from crawler.spiders.spider import NewsRAGSpider

def run_spider(site_url):
    """Hàm này chạy trong một Process riêng cho mỗi trang báo"""
    settings = get_project_settings()
    process = CrawlerProcess(settings)
    # Truyền trực tiếp start_urls vào Spider
    process.crawl(NewsRAGSpider, start_urls=[site_url])
    process.start()

def run_consumer():
    """Hàm này chạy trong một Process riêng để hốt dữ liệu từ Kafka"""
    print("[Consumer] Đang khởi tạo kết nối...")
    time.sleep(2) 
    consumer_module.start_processing()

if __name__ == "__main__":
    # 1. Cấu hình Multiprocessing sạch (Cực quan trọng trên Arch)
    multiprocessing.set_start_method('spawn', force=True)

    # 2. Đọc danh sách các trang báo từ config
    config_path = 'crawler/spiders/config_site.json'
    if not os.path.exists(config_path):
        print(f" Không tìm thấy file config tại: {config_path}")
        exit(1)

    with open(config_path, 'r', encoding='utf-8') as f:
        sites = json.load(f)
    
    # Chuẩn hóa danh sách URL (chấp nhận cả string và dict)
    urls = [s['url'] if isinstance(s, dict) else s for s in sites]

    all_processes = []

    try:
        # 3. CHẠY CONSUMER TRƯỚC (Để đợi sẵn dữ liệu từ Kafka)
        p_cons = multiprocessing.Process(target=run_consumer, name="Consumer-Process")
        p_cons.start()
        all_processes.append(p_cons)
        print("Consumer đã sẵn sàng.")
        
        time.sleep(5) # Đợi Consumer ổn định Group ID

        # 4. CHẠY CÁC SPIDER SONG SONG (Mỗi trang 1 Process)
        print(f"Bắt đầu kích hoạt {len(urls)} Spiders...")
        spider_processes = []
        for url in urls:
            p_spider = multiprocessing.Process(target=run_spider, args=(url,), name=f"Spider-{url}")
            p_spider.start()
            spider_processes.append(p_spider)
            all_processes.append(p_spider)

        # 5. Đợi các Spider hoàn thành nhiệm vụ
        for p in spider_processes:
            p.join()
        
        print("Tất cả Spiders đã cào xong. Đợi Consumer xử lý nốt bài cuối...")
        time.sleep(30) # Cho Consumer thêm thời gian để "tiêu hóa" nốt đống bài cuối

        # 6. Dừng Consumer
        p_cons.terminate()
        p_cons.join()
        print("Hệ thống đã dừng sạch sẽ.")

    except KeyboardInterrupt:
        print("\nNgười dùng yêu cầu dừng hệ thống...")
        for p in all_processes:
            if p.is_alive():
                p.terminate()
                p.join()