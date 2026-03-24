----- DIM TABLE -----
CREATE TABLE IF NOT EXISTS dim_source (
    source_id SERIAL PRIMARY KEY,
    domain TEXT UNIQUE
);


CREATE SEQUENCE IF NOT EXISTS dim_time_time_id_seq START 0 MINVALUE 0;
CREATE TABLE IF NOT EXISTS dim_time (
    time_id INT PRIMARY KEY DEFAULT nextval('dim_time_time_id_seq'),
    date DATE UNIQUE,
    day INT,
    month INT,
    year INT
);


CREATE TABLE IF NOT EXISTS dim_content (
    content_id SERIAL PRIMARY KEY,
    url_hash TEXT UNIQUE,
    content TEXT
);
CREATE SEQUENCE IF NOT EXISTS dim_author_author_id_seq START 0 MINVALUE 0;
CREATE TABLE IF NOT EXISTS dim_author (
    author_id INT PRIMARY KEY DEFAULT nextval('dim_author_author_id_seq'),
    author_name TEXT UNIQUE
);

-- --- KHỞI TẠO DỮ LIỆU MẶC ĐỊNH ---
-- Chèn sẵn bản ghi Unknown -----
INSERT INTO dim_time (time_id, date, day, month, year)
VALUES (0, '1900-01-01', 1, 1, 1900)
ON CONFLICT (time_id) DO NOTHING;

INSERT INTO dim_author (author_id, author_name)
VALUES (0, 'Unknown')
ON CONFLICT (author_id) DO NOTHING;


----- FACT TABLE -----
CREATE TABLE IF NOT EXISTS fact_articles (
    article_id SERIAL PRIMARY KEY,
    url_hash TEXT UNIQUE,
    title TEXT,
    source_id INT REFERENCES dim_source(source_id),
    time_id INT REFERENCES dim_time(time_id),
    content_id INT REFERENCES dim_content(content_id),
    content_length INT
);

----- Article-Author ----- (Bảng trung gian cho trường hợp 1 bài viết N tác giả)
CREATE TABLE IF NOT EXISTS fact_article_authors (
    article_id INT REFERENCES fact_articles(article_id),
    author_id INT REFERENCES dim_author(author_id),
    PRIMARY KEY (article_id, author_id)
);

----- CHUNK TABLE -----
CREATE TABLE IF NOT EXISTS fact_chunks (
    chunk_id SERIAL PRIMARY KEY,
    article_id INT REFERENCES fact_articles(article_id),
    chunk_index INT,
    content TEXT
);

----- INDEXES -----
CREATE INDEX IF NOT EXISTS idx_source_domain 
ON dim_source(domain);

CREATE INDEX IF NOT EXISTS idx_time_date 
ON dim_time(date);

CREATE INDEX IF NOT EXISTS idx_article_hash 
ON fact_articles(url_hash);

CREATE INDEX IF NOT EXISTS idx_chunks_article 
ON fact_chunks(article_id);


