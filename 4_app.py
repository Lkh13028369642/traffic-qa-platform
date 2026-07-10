import streamlit as st
import pandas as pd
import plotly.express as px
import duckdb

# ============ 把问答引擎直接集成在这里，不再需要外部导入 ============
class TrafficQAAgent:
    def __init__(self):
        self.conn = duckdb.connect('traffic.duckdb')
        print("✅ 问答引擎启动成功")

    def generate_sql(self, question):
        q = question.lower()
        
        if '车速' in q or '速度' in q:
            if '平均' in q:
                return "SELECT road_name, AVG(avg_speed_kmh) as 平均车速 FROM traffic_fact GROUP BY road_name ORDER BY 平均车速 ASC LIMIT 10"
            if '最高' in q or '最快' in q:
                return "SELECT road_name, MAX(avg_speed_kmh) as 最高车速 FROM traffic_fact GROUP BY road_name ORDER BY 最高车速 DESC LIMIT 3"
            return "SELECT road_name, AVG(avg_speed_kmh) as 平均车速 FROM traffic_fact GROUP BY road_name LIMIT 10"

        if '拥堵' in q:
            if '指数' in q or '最堵' in q:
                return "SELECT road_name, AVG(congestion_index) as 拥堵指数 FROM traffic_fact GROUP BY road_name ORDER BY 拥堵指数 DESC LIMIT 5"
            if '高峰' in q:
                return "SELECT peak_flag, AVG(congestion_index) as 平均拥堵指数 FROM traffic_fact GROUP BY peak_flag"
            return "SELECT road_name, AVG(congestion_index) as 平均拥堵指数 FROM traffic_fact GROUP BY road_name ORDER BY 平均拥堵指数 DESC LIMIT 5"

        if '事故' in q:
            if '最多' in q or '高发' in q:
                return "SELECT road_name, COUNT(*) as 事故数量 FROM accident_fact GROUP BY road_name ORDER BY 事故数量 DESC LIMIT 3"
            if '追尾' in q:
                return "SELECT road_name, COUNT(*) as 追尾事故数 FROM accident_fact WHERE accident_type LIKE '%追尾%' GROUP BY road_name"
            return "SELECT road_name, COUNT(*) as 事故总数 FROM accident_fact GROUP BY road_name ORDER BY 事故总数 DESC LIMIT 5"

        if '流量' in q or '车流' in q:
            return "SELECT road_name, SUM(traffic_volume) as 总车流量 FROM traffic_fact GROUP BY road_name ORDER BY 总车流量 DESC LIMIT 5"

        return "SELECT road_name, AVG(avg_speed_kmh) as 平均车速, AVG(congestion_index) as 平均拥堵指数 FROM traffic_fact GROUP BY road_name LIMIT 10"

    def query(self, question):
        sql = self.generate_sql(question)
        print(f"📝 执行SQL: {sql}")
        try:
            df = self.conn.execute(sql).df()
            if df.empty:
                return None, "查询结果为空，请换一种问法。"
            insight = f"✅ 查询成功！共返回 {len(df)} 条记录。"
            return df, insight
        except Exception as e:
            return None, f"数据库查询错误: {str(e)}"
# ============ 引擎代码结束 ============


# ============ 以下是网页界面代码 ============
st.set_page_config(page_title="交管数据问答平台", layout="wide", page_icon="🚦")

st.title("🚦 面向交管部门的交通数据问答分析平台")
st.caption("智能语义查询 · 实时数据分析 · 决策辅助")

@st.cache_resource
def load_agent():
    try:
        return TrafficQAAgent()
    except Exception as e:
        st.error(f"⚠️ 数据库连接失败，请先运行 python 2_database_setup.py 建库。错误: {e}")
        return None

agent = load_agent()

with st.sidebar:
    st.header("📊 数据总览")
    db_ok = False
    if agent is not None:
        try:
            tables = agent.conn.execute("SHOW TABLES").df()
            if not tables.empty and 'traffic_fact' in tables['name'].values:
                total_records = agent.conn.execute("SELECT COUNT(*) FROM traffic_fact").fetchone()[0]
                total_roads = agent.conn.execute("SELECT COUNT(DISTINCT road_name) FROM traffic_fact").fetchone()[0]
                db_ok = True
                st.metric("总记录数", f"{total_records:,}")
                st.metric("监测道路数", total_roads)
            else:
                st.warning("⚠️ 数据表未创建，请运行: python 2_database_setup.py")
        except:
            st.warning("⚠️ 读取数据失败，请检查数据库文件。")
    
    if not db_ok:
        st.error("📌 请先执行 python 2_database_setup.py 初始化数据")
        
    st.divider()
    st.subheader("💡 热门问法示例")
    st.info("• 哪条路最堵？")
    st.info("• 平均车速最慢的路段")
    st.info("• 事故最多的路段Top3")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("🧠 智能问答")
    user_question = st.text_input("请输入您的交管数据问题", placeholder="例如：哪条路最堵？")
    
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        if agent is None:
            st.error("系统未就绪，请先完成数据库初始化。")
        elif user_question:
            with st.spinner("正在分析..."):
                df_result, insight = agent.query(user_question)
            if df_result is not None and not df_result.empty:
                st.session_state['df'] = df_result
                st.session_state['insight'] = insight
                st.session_state['question'] = user_question
            else:
                st.error(f"分析失败: {insight}")
        else:
            st.warning("请输入您的问题")

with col2:
    st.subheader("📈 分析结果展示")
    if 'df' in st.session_state and st.session_state['df'] is not None:
        df = st.session_state['df']
        st.success(f"💬 解读: {st.session_state.get('insight', '')}")
        
        tab1, tab2 = st.tabs(["📊 可视化图表", "📋 原始数据表格"])
        with tab1:
            if 'road_name' in df.columns and len(df) <= 20:
                numeric_col = df.select_dtypes(include='number').columns[0] if not df.select_dtypes(include='number').empty else None
                if numeric_col:
                    fig = px.bar(df, x='road_name', y=numeric_col, title="分析结果", color='road_name', text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)
                elif '事故数量' in df.columns:
                    fig = px.pie(df, names='road_name', values='事故数量', title="事故分布")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                numeric_cols = df.select_dtypes(include='number').columns
                if len(numeric_cols) > 0:
                    fig = px.line(df, y=numeric_cols[0], title="趋势图")
                    st.plotly_chart(fig, use_container_width=True)
        with tab2:
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 下载CSV", data=csv, file_name="query_result.csv", mime="text/csv")
    else:
        st.info("👈 输入问题并点击按钮，结果将在这里显示。")

st.divider()
st.caption("⚠️ 本平台为演示原型，所有数据均为模拟生成。")