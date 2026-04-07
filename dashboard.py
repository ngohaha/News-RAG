import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime

# --- CẤU HÌNH KẾT NỐI ---
PG_CONFIG = {
    "dbname": "news_rag",
    "user": "tuan",
    "password": "tuan",
    "host": "localhost", # Đổi thành "postgres_news_rag" nếu chạy trong mạng Docker
    "port": "5432"
}

@st.cache_resource(ttl=10)
def get_connection():
    return psycopg2.connect(**PG_CONFIG)

def run_query(query):
    try:
        conn = get_connection()
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Lỗi truy vấn: {e}")
        return pd.DataFrame()

# --- GIAO DIỆN STREAMLIT ---
st.set_page_config(page_title="News RAG Monitor", layout="wide", page_icon="🗄️")

st.title("📊 News RAG Data Warehouse Monitor")
st.markdown(f"**Cập nhật lúc:** {datetime.now().strftime('%H:%M:%S')}")

# --- PHẦN 1: TỔNG QUAN (METRICS) ---
st.subheader("🚀 Hệ thống Metrics")
query_metrics = """
SELECT 
    (SELECT COUNT(*) FROM fact_articles) AS bai_bao,
    (SELECT COUNT(*) FROM fact_chunks) AS tong_chunks,
    (SELECT COUNT(*) FROM article_metadata WHERE publish_date = 'Unknown') AS loi_ngay;
"""
df_m = run_query(query_metrics)
if not df_m.empty:
    m1, m2, m3, m4 = st.columns(4)
    bai_bao = df_m['bai_bao'][0]
    chunks = df_m['tong_chunks'][0]
    
    m1.metric("Bài báo đã xử lý", f"{bai_bao:,}")
    m2.metric("Tổng số Chunks", f"{chunks:,}")
    m3.metric("Chunks trung bình", round(chunks/bai_bao, 2) if bai_bao > 0 else 0)
    m4.metric("Lỗi định dạng ngày", df_m['loi_ngay'][0], delta_color="inverse")

st.divider()

# --- PHẦN 2: CHI TIẾT THEO TỪNG MỤC (TABS) ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📑 Bài báo & Tác giả", 
    "🧩 Chi tiết Chunks", 
    "📅 Thống kê thời gian", 
    "🛠️ Quản trị hệ thống"
])

with tab1:
    st.subheader("Danh sách bài báo và tác giả")
    query_art = """
    SELECT f.title, STRING_AGG(a.author_name, ' & ') as authors 
    FROM fact_articles f 
    JOIN fact_article_authors faa ON f.article_id = faa.article_id 
    JOIN dim_author a ON faa.author_id = a.author_id 
    GROUP BY f.article_id, f.title 
    ORDER BY f.article_id DESC LIMIT 20;
    """
    st.dataframe(run_query(query_art), use_container_width=True)

with tab2:
    st.subheader("Kiểm tra Chunks của bài báo gần nhất")
    query_chunk = """
    SELECT chunk_index, content
    FROM fact_chunks 
    WHERE article_id = (SELECT MAX(article_id) FROM fact_articles) 
    ORDER BY chunk_index;
    """
    df_chunks = run_query(query_chunk)
    if not df_chunks.empty:
        st.write(f"Đang hiển thị chunks của bài báo ID mới nhất")
        st.table(df_chunks)
    else:
        st.info("Chưa có dữ liệu chunks.")

with tab3:
    st.subheader("Phân bố bài viết theo thời gian")
    query_time = """
    SELECT year, month, COUNT(*) as so_luong
    FROM dim_time 
    JOIN fact_articles ON dim_time.time_id = fact_articles.time_id 
    GROUP BY year, month 
    ORDER BY year DESC, month DESC;
    """
    df_time = run_query(query_time)
    if not df_time.empty:
        st.bar_chart(data=df_time, x="month", y="so_luong")
        st.dataframe(df_time, use_container_width=True)

with tab4:
    st.subheader("Kiểm tra lỗi & Dọn dẹp")
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.warning("Bài báo bị lỗi ngày (Unknown)")
        query_err = "SELECT title, url FROM article_metadata WHERE publish_date = 'Unknown' LIMIT 10;"
        st.dataframe(run_query(query_err), use_container_width=True)
    
    with col_b:
        st.error("Khu vực nguy hiểm")
        if st.button("RESET KHO DỮ LIỆU (TRUNCATE)"):
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("TRUNCATE TABLE article_metadata, dim_source, dim_time, dim_author, dim_content, fact_articles, fact_article_authors, fact_chunks RESTART IDENTITY CASCADE;")
                conn.commit()
                st.success("Đã reset toàn bộ database!")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi reset: {e}")

# Tự động refresh sau 10 giây
import time
time.sleep(10)
st.rerun()