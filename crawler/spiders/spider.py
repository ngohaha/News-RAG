import os
import json
import re
import platform
import scrapy
from newspaper import Article
from dateutil import parser as date_parser
from datetime import datetime

class NewsRAGSpider(scrapy.Spider):
    name = 'news_rag_spider'
    
    # Check OS để cấu hình User-Agent và hiệu năng
    is_windows = platform.system() == "Windows"
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 16 if is_windows else 32,
        'DOWNLOAD_DELAY': 1.0 if is_windows else 0.5,
        'DEPTH_LIMIT': 5,
        'ROBOTSTXT_OBEY': False,
        'LOG_LEVEL': 'INFO',
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            if is_windows else
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Lấy đường dẫn tuyệt đối bất kể OS
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        config_filename = 'config_site.json'
        config_path = os.path.join(curr_dir, config_filename)
        
        # Fix lỗi đường dẫn trên Windows (chuẩn hóa dấu \ và /)
        config_path = os.path.abspath(config_path)

        if not os.path.exists(config_path):
            self.logger.error(f"Không tìm thấy file: {config_path}")
            return

        with open(config_path, 'r', encoding='utf-8') as f:
            sites = json.load(f)

        self.start_urls = [s['url'] if isinstance(s, dict) else s for s in sites]

    def parse(self, response):
        curr_domain = scrapy.utils.url.parse_url(response.url).netloc
        all_links = response.css('a::attr(href)').getall()
        
        for link in all_links:
            # BƯỚC QUAN TRỌNG: Loại bỏ link rác ngay từ đầu
            if any(link.startswith(x) for x in ['mailto:', 'tel:', 'javascript:', '#']):
                continue
                
            full_url = response.urljoin(link)
            
            # Chỉ xử lý nếu cùng domain
            if curr_domain in full_url:
                # 1. Nếu là bài viết
                if any(ext in full_url for ext in ['.html', '.htm', '.amp']):
                    yield response.follow(full_url, callback=self.parse_article)
                
                # 2. Nếu là chuyên mục (đào sâu thêm)
                elif len(full_url.replace('https://' + curr_domain, '').split('/')) <= 3:
                    yield response.follow(full_url, callback=self.parse)

    def parse_article(self, response):
        article = Article(response.url)
        article.set_html(response.text)
        try:
            article.parse()
        except:
            return

        if not article.text or len(article.text) < 100:
            return

        # Trích xuất tác giả
        author = article.authors[0] if article.authors else "Unknown"
        
        # Xử lý ngày tháng linh hoạt
        p_date = article.publish_date
        if not p_date:
            # Tìm trong meta tag hoặc các class phổ biến của báo VN
            raw_date = (
                response.css('meta[property*="published_time"]::attr(content)').get() or
                response.css('span.date::text').get() or
                response.css('.date::text').get()
            )
            if raw_date:
                try:
                    # Regex tìm định dạng dd/mm/yyyy hoặc dd-mm-yyyy
                    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', raw_date)
                    if match:
                        d, m, y = match.groups()
                        p_date = datetime(int(y), int(m), int(d))
                    else:
                        # Dùng parser tự động nếu regex không ra
                        p_date = date_parser.parse(raw_date, fuzzy=True)
                except:
                    p_date = None

        yield {
            'title': article.title.strip(),
            'content': article.text.strip(),
            'url': response.url,
            'source': scrapy.utils.url.parse_url(response.url).netloc,
            'author': author,
            'publish_date': p_date.strftime("%Y-%m-%d %H:%M:%S") if p_date else "Unknown"
        }