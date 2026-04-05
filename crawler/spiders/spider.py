import os
import json
import re
import scrapy
from newspaper import Article
from dateutil import parser as date_parser
from datetime import datetime

class NewsRAGSpider(scrapy.Spider):
    name = 'news_rag_spider'
    custom_settings = {
        'CONCURRENT_REQUESTS': 32,
        'DOWNLOAD_DELAY': 0.8,
        'DEPTH_LIMIT': 5,
        'MEMUSAGE_LIMIT_MB': 512,
        # 'ROBOTSTXT_OBEY': True,
        'ROBOTSTXT_OBEY': False,
        'LOG_LEVEL': 'INFO',
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' # THÊM DÒNG NÀY
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

        # ----- AUTHOR -----
        author_list = article.authors
        author = ", ".join(author_list).strip() if author_list else ""

        if not author:
            author = (
                response.css('p.author_mail strong::text').get() or
                response.css('article.fck_detail p[style*="text-align:right"] strong::text').get() or
                response.css('.author::text').get()
            )

        author = author.strip() if author else "Unknown"

        # ----- PUBLISH DATE -----
        p_date = article.publish_date
        if not p_date:
            raw_date = (
                response.css('meta[property="article:published_time"]::attr(content)').get()
                or response.css('span.date::text').get()   
                or response.css('div.author-time span::text').get()  
            )
            if raw_date:
                try:
        # 1. Dùng Regex để chỉ lấy các cụm số: Ngày/Tháng/Năm Giờ:Phút
        # Tìm các nhóm số cách nhau bởi / hoặc - hoặc :
                    match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4}).*?(\d{1,2}):(\d{1,2})', raw_date)
                    
                    if match:
                        day, month, year, hour, minute = match.groups()
                        # 2. Tạo đối tượng datetime từ các nhóm số đã bóc tách
                        p_date = datetime(int(year), int(month), int(day), int(hour), int(minute))
                    else:
                        # 3. Fallback: Nếu không tìm thấy format quen thuộc, thử dùng parser mặc định
                        # nhưng đã xóa bỏ các từ tiếng Việt gây nhiễu
                        clean_date = re.sub(r'[^\d/:\s-]', '', raw_date).strip()
                        p_date = date_parser.parse(clean_date, dayfirst=True)
                        
                except Exception as e:
                    print(f"Parse date error: {raw_date} | Lỗi: {e}")
                    p_date = None
        publish_date = p_date.strftime("%Y-%m-%d %H:%M:%S") if p_date else "Unknown"
        
        
        # ----- OUTPUT -----
        yield {
            'title': article.title.strip(),
            'content': article.text.strip(),
            'url': response.url,
            'source': response.url.split('/')[2],
            'author': author,
            'publish_date': publish_date
        }