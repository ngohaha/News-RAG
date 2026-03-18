import psycopg2

conn = psycopg2.connect(
    dbname="news_rag", user="tuan", password="tuan", host="localhost"
)
cur = conn.cursor()

# Drop and recreate with the 'content' column
cur.execute("DROP TABLE IF EXISTS article_metadata;")

cur.execute("""
    CREATE TABLE IF NOT EXISTS article_metadata (
        url_hash TEXT PRIMARY KEY,
        title TEXT,
        url TEXT,
        content TEXT,         -- Added this missing column
        mongo_id TEXT,
        crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")
conn.commit()