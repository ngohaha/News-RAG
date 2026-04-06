import streamlit as st
import pandas as pd
import psycopg2
import time
from datetime import datetime

# --- CẤU HÌNH KẾT NỐI ---
PG_CONFIG = {
    "dbname": "news_rag",
    "user": "tuan",
    "password": "tuan",
    "host": "localhost",
    "port": "5432"
}

def get_data():
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        # Lấy 10 bài mới nhất
        # Thay vì ORDER BY id, hãy dùng publish_date hoặc url_hash
        # Sử dụng Common Table Expression (CTE) để phân nhóm theo source
        query = """
        WITH RankedArticles AS (
            SELECT 
                title, 
                author, 
                publish_date, 
                url,
                split_part(url, '/', 3) as source,
                ROW_NUMBER() OVER (
                    PARTITION BY split_part(url, '/', 3) 
                    ORDER BY publish_date DESC
                ) as rn
            FROM article_metadata
        )
        SELECT title, author, publish_date, url, source
        FROM RankedArticles
        WHERE rn <= 10
        ORDER BY source, publish_date DESC;
        """
        df = pd.read_sql(query, conn)
        
        # Lấy tổng số lượng bài
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM article_metadata")
        total = cur.fetchone()[0]
        
        conn.close()
        return df, total
    except Exception as e:
        st.error(f"Lỗi kết nối Database: {e}")
        return pd.DataFrame(), 0

# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="News RAG Monitor", layout="wide")

st.title("News RAG Real-time Monitor")
st.markdown(f"**Thời gian hiện tại:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Tạo các cột chỉ số (Metrics)
col1, col2, col3 = st.columns(3)

# Lấy dữ liệu
df, total_count = get_data()

with col1:
    st.metric("Tổng số bài báo", f"{total_count} bài")
with col2:
    st.metric("Trạng thái Crawler", "Đang chạy" if total_count > 0 else " Dừng")
with col3:
    # Tính số bài mới trong 1 phút (demo)
    st.metric("Tốc độ trung bình", "~50 bài/phút")

st.divider()

# Hiển thị bảng dữ liệu mới nhất
st.subheader("10 Bài báo mới nhất vừa cập nhật")
if not df.empty:
    st.dataframe(df, use_container_width=True)
else:
    st.write("Chưa có dữ liệu nào được crawl...")

# Tự động làm mới trang mỗi 10 giây
time.sleep(10)
st.rerun()