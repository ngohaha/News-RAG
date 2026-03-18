import os
import json
import scrapy
from newspaper import Article

class NewsRAGSpider(scrapy.Spider):
    name = 'news_rag_spider'
    custom_settings = {
        'CONCURRENT_REQUESTS': 32,
        'DOWNLOAD_DELAY': 0.8,
        'DEPTH_LIMIT': 5,
        'MEMUSAGE_LIMIT_MB': 512,
        'ROBOTSTXT_OBEY': True,
        'LOG_LEVEL': 'INFO',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config_path = os.path.join(os.path.dirname(__file__), 'config_site.json')
        config_path = os.path.normpath(config_path)
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Không tìm thấy cấu hình site: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            sites = json.load(f)

        self.start_urls = []
        for site in sites:
            if isinstance(site, dict) and 'url' in site:
                self.start_urls.append(site['url'])
            elif isinstance(site, str):
                self.start_urls.append(site)

        if not self.start_urls:
            raise ValueError('Danh sách start_urls trống. Kiểm tra config_site.json')

        #self.allowed_domains = [scrapy.utils.url.parse_url(url).netloc for url in self.start_urls if url]

    def parse(self, response):
        # 1. Lấy TẤT CẢ các link trên trang
        all_links = response.css('a::attr(href)').getall()
        
        for link in all_links:
            full_url = response.urljoin(link)
            
            # ĐIỀU KIỆN 1: Nếu là bài viết (có đuôi .html) -> Gửi sang parse_article
            if full_url.endswith('.html') and 'vnexpress.net' in full_url:
                yield response.follow(full_url, callback=self.parse_article)
            
            # ĐIỀU KIỆN 2: Nếu là chuyên mục (thời sự, thế giới, kinh doanh...) 
            # Lọc bỏ các link rác như javascript, mailto, hoặc tag
            elif any(cat in full_url for cat in ['/thoi-su', '/the-gioi', '/kinh-doanh', '/giai-tri']) \
                 and 'vnexpress.net' in full_url \
                 and '#' not in full_url:
                # Gửi ngược lại hàm parse để nó tiếp tục tìm link bài viết trong chuyên mục đó
                yield response.follow(full_url, callback=self.parse)

    def parse_article(self, response):
        article = Article(response.url)
        article.set_html(response.text)
        try:
            article.parse()
        except Exception:
            return

        if not article.text:
            return

        yield {
            'title': article.title,
            'content': article.text,
            'url': response.url,
            'source': response.url.split('/')[2]
        }