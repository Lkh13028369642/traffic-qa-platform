import streamlit as st
import pandas as pd
import plotly.express as px
import duckdb

# ============ 问答引擎 ============
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


# ============ 非结构化数据检索（演示） ============
class DocumentRetriever:
    def __init__(self):
        # 模拟事故报告文档
        self.docs = [
            "2026年7月15日，内环高架近XX路出口，发生一起三车追尾事故，造成2人轻伤，事故原因为前车急刹。",
            "2026年7月14日，延安路隧道内，一辆货车因爆胎撞向护栏，导致隧道封闭1小时。",
            "2026年7月13日，南北高架近YY路，发生一起变道刮擦事故，无人员伤亡。",
            "2026年7月12日，中环路某路段，因路面湿滑导致三车连环相撞，1人受伤。",
            "2026年7月11日，世纪大道与XX路交叉口，行人闯红灯被撞，1人重伤。",
            "2026年7月10日，内环高架近ZZ路出口，发生多车连环追尾，涉及车辆5辆，3人轻伤。"
        ]
    
    def search(self, keyword):
        if not keyword:
            return []
        results = [doc for doc in self.docs if keyword in doc]
        return results


# ============ 页面配置 ============
st.set_page_config(page_title="交管数据问答平台", layout="wide", page_icon="🚦")

st.title("🚦 面向交管部门的交通数据问答分析平台")
st.caption("智能语义查询 · 多轮对话 · 多源数据融合")

# 初始化
@st.cache_resource
def load_agent():
    try:
        return TrafficQAAgent()
    except Exception as e:
        st.error(f"⚠️ 数据库连接失败，请先运行 python 2_database_setup.py 建库。错误: {e}")
        return None

@st.cache_resource
def load_retriever():
    return DocumentRetriever()

agent = load_agent()
retriever = load_retriever()

# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []
if "mode" not in st.session_state:
    st.session_state.mode = "SQL问答"


# ============ 侧边栏 ============
with st.sidebar:
    st.header("📊 数据总览")
    
    # 数据概览
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
                st.warning("⚠️ 数据表未创建")
        except:
            st.warning("⚠️ 读取数据失败")
    
    if not db_ok:
        st.error("📌 请先执行 python 2_database_setup.py 初始化数据")
    
    st.divider()
    
    # ===== 模式切换（新增） =====
    st.subheader("🔀 功能模式")
    mode = st.radio(
        "选择分析模式",
        ["📊 SQL问答", "📄 文档检索（演示）"],
        index=0 if st.session_state.mode == "SQL问答" else 1
    )
    st.session_state.mode = mode
    
    st.divider()
    
    # ===== 快捷分析（新增） =====
    st.subheader("⚡ 快捷分析")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 路况简报", use_container_width=True):
            if agent:
                df, insight = agent.query("各道路拥堵情况")
                if df is not None:
                    st.session_state['quick_result'] = df
                    st.session_state['quick_insight'] = insight
                    st.session_state['quick_title'] = "📊 路况简报"
                else:
                    st.error(insight)
    
    with col2:
        if st.button("🚨 事故热点", use_container_width=True):
            if agent:
                df, insight = agent.query("事故最多的路段Top3")
                if df is not None:
                    st.session_state['quick_result'] = df
                    st.session_state['quick_insight'] = insight
                    st.session_state['quick_title'] = "🚨 事故热点分析"
                else:
                    st.error(insight)
    
    if st.button("📈 信控优化建议", use_container_width=True):
        st.session_state['quick_result'] = None
        st.session_state['quick_insight'] = None
        st.session_state['quick_title'] = "📈 信控优化建议"
        st.session_state['quick_text'] = """
基于流量数据分析，建议对以下路口信号灯配时进行优化：

1. **内环高架-XX路交叉口**：早高峰流量增加12%，建议绿灯延长15秒
2. **延安路-YY路交叉口**：晚高峰排队过长，建议启用潮汐车道
3. **南北高架-ZZ路出口**：事故频发，建议增加警示标识和减速带
"""
    
    st.divider()
    
    # ===== 对话历史（新增） =====
    st.subheader("💬 对话历史")
    if st.session_state.messages:
        for msg in st.session_state.messages[-5:]:
            if msg["role"] == "user":
                st.write(f"🧑 **你**: {msg['content'][:30]}..." if len(msg['content']) > 30 else f"🧑 **你**: {msg['content']}")
            else:
                st.write(f"🤖 **系统**: {msg['content'][:30]}..." if len(msg['content']) > 30 else f"🤖 **系统**: {msg['content']}")
        if st.button("🗑️ 清空对话"):
            st.session_state.messages = []
            st.rerun()
    else:
        st.caption("暂无对话记录")


# ============ 主区域 ============

# ---- 模式1：SQL问答（优化为多轮对话） ----
if st.session_state.mode == "📊 SQL问答":
    
    # 显示快捷分析结果
    if 'quick_result' in st.session_state and st.session_state.get('quick_result') is not None:
        with st.container():
            st.subheader(st.session_state.get('quick_title', '分析结果'))
            df = st.session_state['quick_result']
            st.success(f"💬 {st.session_state.get('quick_insight', '')}")
            st.dataframe(df, use_container_width=True)
            # 如果有图表列，自动绘图
            if 'road_name' in df.columns and len(df) <= 20:
                numeric_col = df.select_dtypes(include='number').columns[0] if not df.select_dtypes(include='number').empty else None
                if numeric_col:
                    fig = px.bar(df, x='road_name', y=numeric_col, title=st.session_state.get('quick_title', ''), color='road_name', text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)
        st.divider()
        # 清除快捷结果，避免重复显示
        # st.session_state['quick_result'] = None  # 保留以便刷新后还能看到
    
    if 'quick_text' in st.session_state and st.session_state.get('quick_text'):
        with st.container():
            st.subheader(st.session_state.get('quick_title', '建议'))
            st.info(st.session_state['quick_text'])
        st.divider()
        st.session_state['quick_text'] = None
    
    # 显示对话历史
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # 输入框
    if prompt := st.chat_input("请输入您的交通数据问题（如：哪条路最堵？）"):
        # 保存用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        
        # 调用引擎
        with st.chat_message("assistant"):
            with st.spinner("正在分析数据..."):
                if agent is None:
                    st.error("系统未就绪，请先完成数据库初始化。")
                else:
                    df_result, insight = agent.query(prompt)
                    if df_result is not None and not df_result.empty:
                        # 构建回复
                        response = f"{insight}\n\n"
                        # 显示数据表格
                        st.dataframe(df_result, use_container_width=True)
                        # 如果有图表列，自动绘图
                        if 'road_name' in df_result.columns and len(df_result) <= 20:
                            numeric_col = df_result.select_dtypes(include='number').columns[0] if not df_result.select_dtypes(include='number').empty else None
                            if numeric_col:
                                fig = px.bar(df_result, x='road_name', y=numeric_col, title="查询结果", color='road_name', text_auto=True)
                                st.plotly_chart(fig, use_container_width=True)
                        # 保存到会话
                        st.session_state.messages.append({"role": "assistant", "content": f"{insight}"})
                    else:
                        st.error(f"查询失败: {insight}")
                        st.session_state.messages.append({"role": "assistant", "content": f"查询失败: {insight}"})


# ---- 模式2：文档检索（新增 - 应对非结构化数据） ----
else:
    st.subheader("📄 事故报告文档检索（演示）")
    st.info("""
    💡 **功能说明**：此模块演示系统对**非结构化数据**（如事故报告、执法记录、视频文本等）的检索能力。
    
    实际系统中，可通过 **向量数据库 + RAG（检索增强生成）** 技术，实现对海量文档、图片、视频的语义检索。
    """)
    
    # 显示示例文档
    with st.expander("📁 查看示例事故报告（共6条）"):
        for i, doc in enumerate(retriever.docs, 1):
            st.write(f"{i}. {doc}")
    
    # 搜索框
    search_keyword = st.text_input("🔍 输入关键词检索（如：追尾、内环、隧道）", placeholder="例如：追尾")
    
    if search_keyword:
        results = retriever.search(search_keyword)
        if results:
            st.success(f"✅ 找到 {len(results)} 条相关记录：")
            for r in results:
                with st.container():
                    st.write(f"📌 {r}")
                    # 高亮关键词
                    highlighted = r.replace(search_keyword, f"**{search_keyword}**")
                    st.caption(f"→ {highlighted}")
                    st.divider()
        else:
            st.warning("未找到包含该关键词的记录，请尝试其他关键词。")
    else:
        st.caption("👆 输入关键词后点击检索，系统将搜索事故报告文档。")
    
    # 展示技术路线
    with st.expander("🛠️ 技术路线说明（给老师看）"):
        st.markdown("""
        ### 非结构化数据处理方案
        
        | 数据类型 | 处理方式 | 技术栈 |
        |:---|:---|:---|
        | **事故报告文本** | 文档切片 → 向量化 → 语义检索 | LangChain + Chroma |
        | **交通视频** | 抽帧 → 图像向量化 → 场景检索 | CLIP + 向量数据库 |
        | **雷达点云** | 特征提取 → 结构化存储 | LiDAR处理库 |
        | **社交媒体文本** | 情感分析 → 事件抽取 | 大模型微调 |
        
        **当前演示**：基于关键词匹配的文档检索
        **生产方案**：基于向量数据库的语义检索 + RAG
        """)


# ============ 页脚 ============
st.divider()
st.caption("⚠️ 本平台为演示原型，所有数据均为模拟生成。支持多轮对话、SQL问答、文档检索三大核心能力。")
