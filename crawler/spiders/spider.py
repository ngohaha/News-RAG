import os
import json
import re
import platform
import scrapy
from newspaper import Article
from datetime import datetime

class NewsRAGSpider(scrapy.Spider):
    name = 'news_rag_spider'
    
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
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        config_filename = 'config_site.json'
        config_path = os.path.abspath(os.path.join(curr_dir, config_filename))

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
            if any(link.startswith(x) for x in ['mailto:', 'tel:', 'javascript:', '#']):
                continue
                
            full_url = response.urljoin(link)
            
            if curr_domain in full_url:
                if any(ext in full_url for ext in ['.html', '.htm', '.amp']):
                    yield response.follow(full_url, callback=self.parse_article)
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

        # ----- AUTHOR (Quét mẻ lưới lớn các định dạng lạ) -----
        author_list = article.authors
        author = ", ".join(author_list).strip() if author_list else ""

        # --- MÀNG LỌC THÔNG MINH ---
        def is_valid_author(name):

            clean_name = name.strip()
            # 1. Chặn các đề mục, tựa đề bài viết liên quan (Chứa dấu ? hoặc !)
            if re.match(r'^\d+[\.\-\)]', clean_name) or '?' in clean_name or '!' in clean_name:
                return False


            if not name or len(name) < 2 or len(name) > 100:
                return False
            
            if len(re.findall(r'\d', name)) >= 7:
                return False
            name_lower = name.lower()

            if re.match(r'^\d+[\.\-\)]', name.strip()):
                return False
            
            # Chặn ngày/giờ (VD: 15/12/2023, 04:22)
            if re.search(r'\d{1,2}[/-]\d{1,2}|\d{1,2}:\d{1,2}', name):
                return False
            
            if len(clean_name.split()) > 6 and not any(d in name_lower for d in [',', '-', 'và', '&']):
                # Ngoại lệ: Cho phép lọt nếu nó là tên cơ quan dài (bắt đầu bằng Báo, Tạp chí, Sở, Bộ, Nguồn...)
                if not re.match(r'(?i)^(theo|nguồn|báo|tạp chí|đài|ban|ủy ban|sở|bộ)', clean_name):
                    return False
                
            # BỘ LỌC TỪ KHÓA CẤM
            bad_words = [
                'thứ hai', 'thứ ba', 'thứ tư', 'thứ năm', 'thứ sáu', 'thứ bảy', 'chủ nhật', 
                'ngày', 'tháng', 'năm', 'phút trước', 'giờ trước',
                'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 
                'september', 'october', 'november', 'december',
                'ảnh:', 'video:', 'xem thêm', 'bản quyền', 'chia sẻ', 'liên hệ', 'hotline', 'sđt', 'thông tin', 'fax', 'telephone'
            ]
            if any(word in name_lower for word in bad_words):
                return False
            return True
        # ---------------------------

        # GIAM LỎNG TÊN TÒA SOẠN: Lưu tạm để dùng làm phương án chót
        fake_authors = [
            'vietnamnet news', 'vietnamnet', 'ban biên tập', 
            'giảm nghèo bền vững', 'dân trí', 'thời sự', 'kinh tế', 'bnvsba'
        ]

        # GIAM LỎNG: Nâng cấp kiểm tra "chứa từ khóa" thay vì "giống y hệt"
        fallback_author = ""
        if author:
            author_lower = author.lower()
            
            # Lệnh any() sẽ quét: Chỉ cần 1 từ trong fake_authors xuất hiện trong author_lower là True
            if any(fake in author_lower for fake in fake_authors) or not is_valid_author(author):
                fallback_author = author
                author = "" # Đánh rỗng để ép chạy mẻ lưới CSS bên dưới
            elif not is_valid_author(author):
                author = "" # Nếu tên tác giả ban đầu không hợp lệ, cũng đánh rỗng để chạy mẻ lưới CSS

        if not author:
            # MẺ LƯỚI BẮN TỈA CHUYÊN SÂU
            author_selectors = [
                # Các class đặc thù nhóm tác giả
                response.css('a[href*="tac-gia"]::text').getall(),
                response.css('a[rel="author"]::text').getall(),
                response.css('.news-detail-project::text').get(),
                response.css('.news-detail-project *::text').getall(),
                response.css('div.relative.font-medium::text').get(),
                response.css('[rel="author"]::text').get(),
                
                # Bắn tỉa thẻ link "tac-gia"
                response.css('div.name a[href*="tac-gia"]::text').get(),
                response.css('div.name a[href*="tac-gia"]::attr(title)').get(),

                response.css('a[href*="tac-gia"]::text').get(),
                response.css('a[href*="tac-gia"]::attr(title)').get(),
                
                response.css('span.t1::text, span.t2::text, span.t3::text, span.t4::text, span.t5::text, span.t6::text').get(),
                response.css('.author-info .name::text').get(), 
                # Các class phổ biến
                response.css('.author-name::text').get(),
                response.css('.author-name a::text').get(),

                response.css('.author-info .name::text').get(),
                response.css('.detail-author::text').get(),
                response.css('.tacgia::text').get(),
                response.css('.tac-gia::text').get(),
                response.css('.post-author::text').get(),
                response.css('.article-author::text').get(),
                response.css('.author::text').get(),
                response.css('[itemprop="author"] [itemprop="name"]::text').get(),
                response.css('[rel="author"]::text').get(),

                # Định dạng căn lề phải
                response.css('p[style*="text-align:right"] strong::text').get(),
                response.css('p[style*="text-align: right"] strong::text').get(),
                response.css('div[style*="text-align: right"] strong::text').get(),
                response.css('p.t-a-r strong::text').get(),
                response.css('p.t-a-r b::text').get()
            ]
            
            for a in author_selectors:
                if isinstance(a, list):
                    a = " ".join([t.strip() for t in a if t and t.strip()])
                    
                if a and isinstance(a, str) and a.strip() and a.strip() != "Unknown":
                    # Cắt bỏ ngày tháng dính kèm
                    clean_a = a.split('•')[0].strip()
                    clean_a = re.sub(r'(?i)(?:hotline|liên hệ|sđt|đt)?\s*:?\s*(?:0|\+84)[\d\s.-]{8,12}', '', clean_a)
                    clean_a = re.sub(r'^-|-$', '', clean_a).strip()
                    
                    if is_valid_author(clean_a):
                        author = clean_a
                        break
        
        
        if not author or author == "Unknown":
            # 1. Khoanh vùng nội dung chính
            main_content = response.css('div[class*="content"], article, div[id*="content"], .post-body, .detail-content, .main-content')
            target_area = main_content if main_content else response
            
            # 2. Lấy 15 thẻ <p> hoặc <div> ở khu vực cuối bài
            bottom_nodes = target_area.xpath('.//p | .//div[contains(@class, "author") or contains(@class, "right") or contains(@style, "right") or contains(@align, "right")]')
            
            if bottom_nodes:
                for node in reversed(bottom_nodes[-15:]):
                    # TUYỆT CHIÊU: Nối toàn bộ text trong thẻ (kể cả có thẻ con) thành 1 chuỗi hoàn chỉnh
                    full_text = node.xpath('normalize-space(.)').get()
                    if not full_text: 
                        continue
                        
                    # Dọn dẹp ngoặc kép bọc ngoài
                    clean_text = full_text.replace('"', '').replace('“', '').replace('”', '').strip()
                    if len(clean_text) < 2 or len(clean_text) > 100:
                        continue
                        
                    # ƯU TIÊN 1: Bắt chữ "Nguồn:" hoặc "Theo" (Bất chấp có in đậm hay lề phải hay không)
                    match_source = re.search(r'(?i)(?:Nguồn|Theo|Source)\s*:?\s*(.+)', clean_text)
                    if match_source:
                        candidate = match_source.group(1).strip()
                        if is_valid_author(candidate):
                            author = candidate
                            break
                            
                    # ƯU TIÊN 2: Không có chữ "Nguồn", nhưng Node đó có in đậm hoặc được căn lề phải
                    is_bold_or_right = node.xpath('.//strong | .//b | .//em') or \
                                       'right' in node.attrib.get('style', '').lower() or \
                                       'right' in node.attrib.get('class', '').lower() or \
                                       'right' in node.attrib.get('align', '').lower() or \
                                       't-a-r' in node.attrib.get('class', '').lower()
                                       
                    if is_bold_or_right and is_valid_author(clean_text):
                        author = clean_text
                        break
        # KẾ HOẠCH C (PHƯƠNG ÁN CHÓT): Dùng lại thẻ Meta hoặc Tên tòa soạn
        if not author or author == "Unknown":
            if fallback_author:
                author = fallback_author
            else:
                meta_author = response.css('meta[name="author"]::attr(content)').get() or response.css('meta[property="article:author"]::attr(content)').get()
                if meta_author and is_valid_author(meta_author.strip()):
                    author = meta_author.strip()

        author = author if author else "Unknown"

        # ----- PUBLISH DATE (Chiến thuật Evaluate All - Duyệt đến khi thành công) -----
        p_date = None
        
        # Tập hợp tất cả các class giấu ngày tháng có thể có
        raw_dates = [
            response.css('meta[property="article:published_time"]::attr(content)').get(),
            response.css('time::attr(datetime)').get(),
            response.css('time::text').get(), # Dân trí E-magazine
            response.css('meta[name="pubdate"]::attr(content)').get(),
            response.css('.publish-date::text').get(), # Vietnamnet
            response.css('.bread-crumb-detail__time::text').get(), # Vietnamnet mobile
            response.css('.bread-crumb__detail-time p::text').get(), # Vietnamnet chuyên đề
            response.css('.bread-crumb__detail-time::text').get(),
            response.css('[data-role="publishdate"]::text').get(),
            response.css('.detail-time div::text').get(),
            response.css('.detail-time::text').get(),
            response.css('span.date::text').get(),
            response.css('.time-now::text').get()
        ]
        
        for raw_date in raw_dates:
            if not raw_date or not raw_date.strip():
                continue
                
            # Làm sạch chuỗi
            clean_date = re.sub(r'\s+', ' ', raw_date).replace('\xa0', ' ').strip()
            
            try:
                # 1. ISO (VD: 2026-04-06 19:33 hoặc 2026-04-06T19:33:00)
                match_iso = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})(?:T|\s+)(\d{1,2}):(\d{1,2})', clean_date)
                if match_iso:
                    y, m, d, h, minute = match_iso.groups()
                    p_date = datetime(int(y), int(m), int(d), int(h), int(minute))
                    break # THÀNH CÔNG -> Thoát vòng lặp ngay!
                
                # 2. Ngày trước Giờ sau (VD: 6/4/2026, 17:02)
                match_vn = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4}).*?(\d{1,2}):(\d{1,2})', clean_date)
                if match_vn:
                    d, m, y, h, minute = match_vn.groups()
                    p_date = datetime(int(y), int(m), int(d), int(h), int(minute))
                    break
                    
                # 3. Giờ trước Ngày sau (VD: 14:29 06/02/2024)
                match_vn_rev = re.search(r'(\d{1,2}):(\d{1,2}).*?(\d{1,2})[/-](\d{1,2})[/-](\d{4})', clean_date)
                if match_vn_rev:
                    h, minute, d, m, y = match_vn_rev.groups()
                    p_date = datetime(int(y), int(m), int(d), int(h), int(minute))
                    break
                    
                # 4. Chỉ có ngày
                match_date = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', clean_date)
                if match_date:
                    d, m, y = match_date.groups()
                    p_date = datetime(int(y), int(m), int(d))
                    break
                    
            except Exception:
                continue # Nếu lỗi ở chuỗi này, bỏ qua và lấy chuỗi tiếp theo
                
        if not p_date:
            p_date = article.publish_date

        publish_date = p_date.strftime("%Y-%m-%d %H:%M:%S") if p_date else "Unknown"

        yield {
            'title': article.title.strip(),
            'content': article.text.strip(),
            'url': response.url,
            'source': scrapy.utils.url.parse_url(response.url).netloc,
            'author': author,
            'publish_date': publish_date
        }