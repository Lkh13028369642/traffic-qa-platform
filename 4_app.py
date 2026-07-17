import streamlit as st
import pandas as pd
import plotly.express as px
import duckdb
from datetime import datetime
import time

# ============ 页面配置 ============
st.set_page_config(
    page_title="交通数据智能分析平台",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ 自定义CSS（让界面更专业） ============
st.markdown("""
<style>
    /* 主标题样式 */
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #1a3a5c 0%, #2d6a9f 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        padding: 0.5rem 0;
    }
    .sub-title {
        font-size: 1rem;
        color: #6b7a8f;
        margin-bottom: 1.5rem;
    }
    /* 状态卡片 */
    .status-card {
        background: #f0f4f8;
        border-radius: 10px;
        padding: 1rem;
        border-left: 4px solid #2d6a9f;
        margin: 0.5rem 0;
    }
    .status-card-success {
        border-left-color: #28a745;
        background: #f0fff4;
    }
    .status-card-warning {
        border-left-color: #ffc107;
        background: #fffcf0;
    }
    /* 对话气泡 */
    .chat-user {
        background: #e8f0fe;
        border-radius: 12px 12px 4px 12px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        float: right;
        clear: both;
    }
    .chat-assistant {
        background: #f1f3f4;
        border-radius: 12px 12px 12px 4px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        max-width: 85%;
        float: left;
        clear: both;
    }
    /* 快捷按钮美化 */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    /* 指标卡片 */
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        text-align: center;
        border: 1px solid #e8ecf0;
    }
    .metric-number {
        font-size: 2rem;
        font-weight: 700;
        color: #1a3a5c;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #6b7a8f;
        margin-top: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

# ============ 问答引擎（增强版） ============
class TrafficQAAgent:
    def __init__(self):
        try:
            self.conn = duckdb.connect('traffic.duckdb')
            self.context = []  # 存储对话上下文
        except Exception as e:
            st.error(f"数据库连接失败: {e}")
            self.conn = None

    def generate_sql(self, question, context=None):
        """基于上下文生成SQL"""
        q = question.lower()
        
        # 上下文增强：如果用户说"它"、"该路段"等，尝试从历史中补全
        if context and len(context) > 0:
            last_query = context[-1].get('question', '') if context else ''
            if '它' in q or '该' in q or '这个' in q:
                # 从历史中提取路段名称
                import re
                road_pattern = r'(内环高架|延安路|南北高架|中环路|华夏路|世纪大道)'
                last_roads = re.findall(road_pattern, last_query)
                if last_roads and '道路' not in q:
                    q = q.replace('它', last_roads[0]).replace('该', last_roads[0]).replace('这个', last_roads[0])
        
        # ----- 车速 / 速度 分析 -----
        if '车速' in q or '速度' in q:
            if '平均' in q:
                return "SELECT road_name, AVG(avg_speed_kmh) as 平均车速 FROM traffic_fact GROUP BY road_name ORDER BY 平均车速 ASC LIMIT 10"
            if '最高' in q or '最快' in q:
                return "SELECT road_name, MAX(avg_speed_kmh) as 最高车速 FROM traffic_fact GROUP BY road_name ORDER BY 最高车速 DESC LIMIT 3"
            if '趋势' in q or '变化' in q:
                return "SELECT date, AVG(avg_speed_kmh) as 日均车速 FROM traffic_fact GROUP BY date ORDER BY date DESC LIMIT 7"
            return "SELECT road_name, AVG(avg_speed_kmh) as 平均车速 FROM traffic_fact GROUP BY road_name LIMIT 10"

        # ----- 拥堵 分析 -----
        if '拥堵' in q:
            if '指数' in q or '最堵' in q:
                return "SELECT road_name, AVG(congestion_index) as 拥堵指数 FROM traffic_fact GROUP BY road_name ORDER BY 拥堵指数 DESC LIMIT 5"
            if '高峰' in q:
                return "SELECT peak_flag, AVG(congestion_index) as 平均拥堵指数, COUNT(*) as 记录数 FROM traffic_fact GROUP BY peak_flag"
            if '排行' in q or '排名' in q:
                return "SELECT road_name, AVG(congestion_index) as 拥堵指数 FROM traffic_fact GROUP BY road_name ORDER BY 拥堵指数 DESC LIMIT 10"
            return "SELECT road_name, AVG(congestion_index) as 平均拥堵指数 FROM traffic_fact GROUP BY road_name ORDER BY 平均拥堵指数 DESC LIMIT 5"

        # ----- 事故 分析 -----
        if '事故' in q:
            if '最多' in q or '高发' in q or '排行' in q:
                return "SELECT road_name, COUNT(*) as 事故数量 FROM accident_fact GROUP BY road_name ORDER BY 事故数量 DESC LIMIT 5"
            if '追尾' in q:
                return "SELECT road_name, COUNT(*) as 追尾事故数 FROM accident_fact WHERE accident_type LIKE '%追尾%' GROUP BY road_name ORDER BY 追尾事故数 DESC"
            if '伤亡' in q:
                return "SELECT road_name, SUM(casualty_count) as 伤亡总数 FROM accident_fact GROUP BY road_name ORDER BY 伤亡总数 DESC LIMIT 5"
            if '趋势' in q or '变化' in q:
                return "SELECT DATE_TRUNC('week', accident_time) as 周, COUNT(*) as 事故数 FROM accident_fact GROUP BY 周 ORDER BY 周 DESC LIMIT 8"
            return "SELECT road_name, COUNT(*) as 事故总数 FROM accident_fact GROUP BY road_name ORDER BY 事故总数 DESC LIMIT 5"

        # ----- 流量 分析 -----
        if '流量' in q or '车流' in q:
            if '排行' in q or '排名' in q:
                return "SELECT road_name, SUM(traffic_volume) as 总车流量 FROM traffic_fact GROUP BY road_name ORDER BY 总车流量 DESC LIMIT 5"
            if '高峰' in q:
                return "SELECT peak_flag, SUM(traffic_volume) as 总流量 FROM traffic_fact GROUP BY peak_flag"
            return "SELECT road_name, SUM(traffic_volume) as 总车流量 FROM traffic_fact GROUP BY road_name ORDER BY 总车流量 DESC LIMIT 5"

        # ----- 综合查询 -----
        if '概况' in q or '总体' in q or '整体' in q:
            return """
                SELECT 
                    '总体概况' as 指标,
                    COUNT(DISTINCT road_name) as 监测道路数,
                    AVG(avg_speed_kmh) as 全市平均车速,
                    AVG(congestion_index) as 全市平均拥堵指数
                FROM traffic_fact
            """
        
        # ----- 对比查询 -----
        if '对比' in q or '比较' in q:
            if '高峰' in q and '平峰' in q:
                return """
                    SELECT peak_flag, 
                           AVG(avg_speed_kmh) as 平均车速,
                           AVG(congestion_index) as 平均拥堵指数,
                           COUNT(*) as 记录数
                    FROM traffic_fact 
                    GROUP BY peak_flag
                """

        # ----- 默认智能推荐 -----
        if '推荐' in q or '建议' in q:
            return "SELECT road_name, AVG(congestion_index) as 拥堵指数 FROM traffic_fact GROUP BY road_name ORDER BY 拥堵指数 DESC LIMIT 3"
            
        return "SELECT road_name, AVG(avg_speed_kmh) as 平均车速, AVG(congestion_index) as 平均拥堵指数 FROM traffic_fact GROUP BY road_name LIMIT 10"

    def query(self, question, context=None):
        """执行问答，支持上下文"""
        if self.conn is None:
            return None, "数据库未连接"
        
        sql = self.generate_sql(question, context)
        print(f"📝 SQL: {sql}")
        
        try:
            df = self.conn.execute(sql).df()
            if df.empty:
                return None, "查询结果为空，请换个问法试试。"
            
            # 智能解读
            insight = self._generate_insight(df, question)
            return df, insight
        except Exception as e:
            return None, f"查询出错: {str(e)}"
    
    def _generate_insight(self, df, question):
        """生成数据洞察"""
        rows = len(df)
        insight = f"✅ 查询成功，共 {rows} 条记录。"
        
        # 针对不同查询类型生成洞察
        if '拥堵指数' in df.columns and not df.empty:
            max_row = df.loc[df['拥堵指数'].idxmax()] if '拥堵指数' in df.columns else None
            if max_row is not None and 'road_name' in max_row.index:
                insight += f" 最拥堵路段为 **{max_row['road_name']}**，拥堵指数 {max_row['拥堵指数']:.1f}。"
        
        if '平均车速' in df.columns and not df.empty:
            min_row = df.loc[df['平均车速'].idxmin()] if '平均车速' in df.columns else None
            if min_row is not None and 'road_name' in min_row.index:
                insight += f" 平均车速最慢为 **{min_row['road_name']}** ({min_row['平均车速']:.1f} km/h)。"
        
        if '事故数量' in df.columns and not df.empty:
            max_acc = df.loc[df['事故数量'].idxmax()] if '事故数量' in df.columns else None
            if max_acc is not None and 'road_name' in max_acc.index:
                insight += f" 事故最多路段为 **{max_acc['road_name']}** ({max_acc['事故数量']} 起)。"
        
        return insight
    
    def get_recommendations(self):
        """生成智能建议"""
        try:
            # 获取最堵路段
            df_congest = self.conn.execute(
                "SELECT road_name, AVG(congestion_index) as 拥堵指数 FROM traffic_fact GROUP BY road_name ORDER BY 拥堵指数 DESC LIMIT 3"
            ).df()
            
            # 获取事故高发路段
            df_acc = self.conn.execute(
                "SELECT road_name, COUNT(*) as 事故数 FROM accident_fact GROUP BY road_name ORDER BY 事故数 DESC LIMIT 3"
            ).df()
            
            recommendations = []
            if not df_congest.empty:
                recommendations.append(f"🚨 重点关注拥堵路段：{', '.join(df_congest['road_name'].tolist())}")
            if not df_acc.empty:
                recommendations.append(f"⚠️ 事故高发路段：{', '.join(df_acc['road_name'].tolist())}")
            
            if not recommendations:
                recommendations.append("✅ 当前路网整体运行平稳，无突出拥堵或事故热点。")
            
            return recommendations
        except:
            return ["无法生成建议，请检查数据完整性。"]


# ============ 非结构化数据检索（增强版） ============
class DocumentRetriever:
    def __init__(self):
        self.docs = [
            {"id": 1, "title": "内环高架追尾事故", "content": "2026年7月15日，内环高架近XX路出口，发生一起三车追尾事故，造成2人轻伤，事故原因为前车急刹。", "type": "事故报告"},
            {"id": 2, "title": "延安路隧道货车事故", "content": "2026年7月14日，延安路隧道内，一辆货车因爆胎撞向护栏，导致隧道封闭1小时。", "type": "事故报告"},
            {"id": 3, "title": "南北高架刮擦事故", "content": "2026年7月13日，南北高架近YY路，发生一起变道刮擦事故，无人员伤亡。", "type": "事故报告"},
            {"id": 4, "title": "中环路连环相撞", "content": "2026年7月12日，中环路某路段，因路面湿滑导致三车连环相撞，1人受伤。", "type": "事故报告"},
            {"id": 5, "title": "世纪大道行人事故", "content": "2026年7月11日，世纪大道与XX路交叉口，行人闯红灯被撞，1人重伤。", "type": "事故报告"},
            {"id": 6, "title": "内环高架多车连环追尾", "content": "2026年7月10日，内环高架近ZZ路出口，发生多车连环追尾，涉及车辆5辆，3人轻伤。", "type": "事故报告"},
            {"id": 7, "title": "交通管制公告", "content": "2026年7月16日，因施工需要，南北高架部分路段将于20:00-06:00封闭。", "type": "公告"},
            {"id": 8, "title": "限行政策调整", "content": "自2026年8月1日起，内环以内工作日限行时段调整为7:00-20:00。", "type": "政策"},
        ]
        self.conversation = []
    
    def search(self, keyword):
        if not keyword or len(keyword.strip()) < 2:
            return []
        results = []
        for doc in self.docs:
            if keyword in doc['content'] or keyword in doc['title']:
                results.append(doc)
        return results
    
    def semantic_search(self, keyword):
        """模拟语义搜索（演示用）"""
        # 简单语义映射：用关键词映射到相关文档
        semantic_map = {
            '追尾': ['内环高架追尾事故', '内环高架多车连环追尾'],
            '货车': ['延安路隧道货车事故'],
            '行人': ['世纪大道行人事故'],
            '施工': ['交通管制公告'],
            '限行': ['限行政策调整'],
            '高架': ['内环高架追尾事故', '南北高架刮擦事故', '内环高架多车连环追尾'],
        }
        matched_titles = []
        for key, titles in semantic_map.items():
            if key in keyword:
                matched_titles.extend(titles)
        # 返回匹配的文档
        if matched_titles:
            return [d for d in self.docs if d['title'] in matched_titles]
        return self.search(keyword)
    
    def get_stats(self):
        return {
            '总文档数': len(self.docs),
            '事故报告': len([d for d in self.docs if d['type'] == '事故报告']),
            '政策公告': len([d for d in self.docs if d['type'] in ['公告', '政策']]),
        }


# ============ 初始化 ============
@st.cache_resource
def load_agent():
    try:
        return TrafficQAAgent()
    except Exception as e:
        return None

@st.cache_resource
def load_retriever():
    return DocumentRetriever()

agent = load_agent()
retriever = load_retriever()

# 会话状态
if "messages" not in st.session_state:
    st.session_state.messages = []
if "mode" not in st.session_state:
    st.session_state.mode = "智能问答"
if "context" not in st.session_state:
    st.session_state.context = []
if "last_query" not in st.session_state:
    st.session_state.last_query = ""


# ============ 侧边栏 ============
with st.sidebar:
    # 系统Logo/标题
    st.markdown("""
    <div style="text-align:center; padding:0.5rem 0 1rem 0;">
        <div style="font-size:3rem;">🚦</div>
        <div style="font-size:1.1rem; font-weight:600; color:#1a3a5c;">交管智能分析</div>
        <div style="font-size:0.75rem; color:#6b7a8f;">v2.0 · 多轮对话</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # 数据状态
    st.subheader("📊 数据概览")
    if agent and agent.conn:
        try:
            tables = agent.conn.execute("SHOW TABLES").df()
            if not tables.empty and 'traffic_fact' in tables['name'].values:
                total_records = agent.conn.execute("SELECT COUNT(*) FROM traffic_fact").fetchone()[0]
                total_roads = agent.conn.execute("SELECT COUNT(DISTINCT road_name) FROM traffic_fact").fetchone()[0]
                st.markdown(f"""
                <div class="status-card status-card-success">
                    <strong>✅ 数据就绪</strong><br>
                    监测道路: <strong>{total_roads}</strong> 条<br>
                    记录总数: <strong>{total_records:,}</strong> 条
                </div>
                """, unsafe_allow_html=True)
            else:
                st.warning("⚠️ 数据表未创建，请运行建库脚本")
        except:
            st.warning("⚠️ 数据读取失败")
    else:
        st.error("❌ 数据库未连接")
    
    st.divider()
    
    # 模式切换
    st.subheader("🔀 分析模式")
    mode = st.radio(
        "",
        ["💬 智能问答", "📄 文档检索"],
        index=0 if st.session_state.mode == "智能问答" else 1
    )
    st.session_state.mode = mode
    
    st.divider()
    
    # 快捷操作（更专业）
    st.subheader("⚡ 快捷分析")
    
    # 使用列布局让按钮更紧凑
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🚦 路况简报", use_container_width=True):
            if agent:
                df, insight = agent.query("各道路拥堵概况")
                if df is not None:
                    st.session_state['quick_result'] = df
                    st.session_state['quick_insight'] = insight
                    st.session_state['quick_title'] = "🚦 路况简报"
                    st.session_state['quick_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with col_b:
        if st.button("🚨 事故热点", use_container_width=True):
            if agent:
                df, insight = agent.query("事故排行")
                if df is not None:
                    st.session_state['quick_result'] = df
                    st.session_state['quick_insight'] = insight
                    st.session_state['quick_title'] = "🚨 事故热点分析"
                    st.session_state['quick_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    col_c, col_d = st.columns(2)
    with col_c:
        if st.button("📈 信控建议", use_container_width=True):
            if agent:
                recs = agent.get_recommendations()
                st.session_state['quick_result'] = None
                st.session_state['quick_insight'] = "📈 基于交通数据生成优化建议"
                st.session_state['quick_title'] = "📈 信号优化建议"
                st.session_state['quick_text'] = "\n".join(recs)
                st.session_state['quick_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    with col_d:
        if st.button("📊 生成报告", use_container_width=True):
            if agent:
                # 生成综合报告
                df_speed, _ = agent.query("全市平均车速")
                df_congest, _ = agent.query("拥堵排行")
                df_acc, _ = agent.query("事故排行")
                report = f"""
                ### 📋 交通运行综合报告
                **报告时间**: {datetime.now().strftime("%Y-%m-%d %H:%M")}
                
                #### 📊 车速概况
                {df_speed.to_string(index=False) if df_speed is not None else '数据暂缺'}
                
                #### 🚦 拥堵热点
                {df_congest.to_string(index=False) if df_congest is not None else '数据暂缺'}
                
                #### 🚨 事故高发路段
                {df_acc.to_string(index=False) if df_acc is not None else '数据暂缺'}
                """
                st.session_state['quick_result'] = None
                st.session_state['quick_insight'] = "📋 综合报告已生成"
                st.session_state['quick_title'] = "📋 综合运行报告"
                st.session_state['quick_text'] = report
                st.session_state['quick_time'] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    st.divider()
    
    # 智能建议（新增 - 显示在侧边栏底部）
    st.subheader("💡 智能建议")
    if agent:
        recs = agent.get_recommendations()
        for rec in recs:
            st.info(rec)
    
    st.divider()
    
    # 对话控制
    if st.session_state.messages:
        if st.button("🗑️ 清空对话", use_container_width=True):
            st.session_state.messages = []
            st.session_state.context = []
            st.rerun()


# ============ 主区域 ============

# ---- 显示当前模式标题 ----
if st.session_state.mode == "💬 智能问答":
    
    # ---- 快捷结果显示 ----
    if 'quick_result' in st.session_state and st.session_state.get('quick_result') is not None:
        with st.container():
            col_title, col_time = st.columns([3, 1])
            with col_title:
                st.subheader(st.session_state.get('quick_title', '分析结果'))
            with col_time:
                if 'quick_time' in st.session_state:
                    st.caption(f"🕐 {st.session_state['quick_time']}")
            
            st.success(f"💬 {st.session_state.get('quick_insight', '')}")
            df = st.session_state['quick_result']
            st.dataframe(df, use_container_width=True)
            
            if 'road_name' in df.columns and len(df) <= 20:
                numeric_col = df.select_dtypes(include='number').columns[0] if not df.select_dtypes(include='number').empty else None
                if numeric_col:
                    fig = px.bar(
                        df, x='road_name', y=numeric_col, 
                        title=st.session_state.get('quick_title', ''),
                        color='road_name', text_auto=True,
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig.update_layout(showlegend=False, height=350)
                    st.plotly_chart(fig, use_container_width=True)
            
            # 添加导出按钮
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 导出CSV", data=csv, file_name=f"analysis_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
        st.divider()
        # 清除，避免重复显示
        if st.button("🔄 关闭结果，继续对话"):
            st.session_state['quick_result'] = None
            st.rerun()
        st.divider()
    
    if 'quick_text' in st.session_state and st.session_state.get('quick_text'):
        with st.container():
            st.subheader(st.session_state.get('quick_title', '分析结果'))
            st.text(st.session_state['quick_text'])
            st.caption(f"🕐 {st.session_state.get('quick_time', '')}")
        st.divider()
        if st.button("🔄 关闭结果"):
            st.session_state['quick_text'] = None
            st.rerun()
        st.divider()
    
    # ---- 对话历史（多轮对话核心） ----
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            # 如果是助手消息且包含数据，显示数据表格
            if msg.get("data") is not None:
                st.dataframe(msg["data"], use_container_width=True)
    
    # ---- 输入框 ----
    if prompt := st.chat_input("请输入交通数据问题（支持多轮对话）"):
        # 保存用户消息
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.context.append({"question": prompt})
        
        with st.chat_message("user"):
            st.write(prompt)
        
        # 调用引擎
        with st.chat_message("assistant"):
            with st.spinner("🔍 正在分析数据..."):
                if agent is None:
                    st.error("系统未就绪，请检查数据库连接。")
                else:
                    df_result, insight = agent.query(prompt, st.session_state.context)
                    
                    if df_result is not None and not df_result.empty:
                        response = insight
                        st.write(response)
                        st.dataframe(df_result, use_container_width=True)
                        
                        # 自动图表
                        if 'road_name' in df_result.columns and len(df_result) <= 20:
                            numeric_col = df_result.select_dtypes(include='number').columns[0] if not df_result.select_dtypes(include='number').empty else None
                            if numeric_col:
                                fig = px.bar(
                                    df_result, x='road_name', y=numeric_col, 
                                    title="📊 查询结果可视化",
                                    color='road_name', text_auto=True,
                                    color_discrete_sequence=px.colors.qualitative.Set2
                                )
                                fig.update_layout(showlegend=False, height=350)
                                st.plotly_chart(fig, use_container_width=True)
                        
                        # 导出
                        csv = df_result.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 导出结果", data=csv, file_name=f"query_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv")
                        
                        # 保存到会话
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": insight,
                            "data": df_result
                        })
                        st.session_state.context.append({"result": insight})
                        st.session_state.last_query = prompt
                    else:
                        st.error(f"查询失败: {insight}")
                        st.session_state.messages.append({"role": "assistant", "content": f"❌ {insight}"})


# ---- 文档检索模式 ----
else:
    st.subheader("📄 非结构化数据检索")
    
    # 显示统计信息
    stats = retriever.get_stats()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📚 文档总数", stats['总文档数'])
    with col2:
        st.metric("📄 事故报告", stats['事故报告'])
    with col3:
        st.metric("📋 政策公告", stats['政策公告'])
    with col4:
        st.metric("🔍 索引字段", "标题+内容")
    
    st.info("""
    💡 **功能说明**：此模块演示系统对**非结构化数据**的检索能力。
    实际系统中可通过 **向量数据库 + RAG（检索增强生成）** 技术，实现对海量文档、图片、视频的语义检索。
    """)
    
    # 搜索区域
    search_type = st.radio("检索方式", ["🔍 关键词检索", "🧠 语义检索（演示）"], horizontal=True)
    
    search_keyword = st.text_input("输入关键词", placeholder="例如：追尾、内环、货车、限行")
    
    col_search, col_clear = st.columns([1, 5])
    with col_search:
        search_clicked = st.button("🔍 检索", use_container_width=True)
    
    if search_clicked and search_keyword:
        with st.spinner("检索中..."):
            if search_type == "🔍 关键词检索":
                results = retriever.search(search_keyword)
            else:
                results = retriever.semantic_search(search_keyword)
            
            if results:
                st.success(f"✅ 找到 {len(results)} 条相关记录")
                for doc in results:
                    with st.container():
                        st.markdown(f"""
                        <div style="background:#f8f9fa; border-radius:8px; padding:1rem; margin:0.5rem 0; border-left:3px solid #2d6a9f;">
                            <strong>📌 {doc['title']}</strong>
                            <span style="background:#e9ecef; padding:0.1rem 0.6rem; border-radius:12px; font-size:0.75rem; margin-left:0.5rem;">{doc['type']}</span>
                            <div style="margin-top:0.3rem; color:#333;">{doc['content']}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.warning("未找到相关记录，请尝试其他关键词")
    
    # 显示所有文档
    with st.expander("📁 查看所有文档"):
        for doc in retriever.docs:
            st.write(f"**{doc['title']}** ({doc['type']})")
            st.caption(doc['content'])
            st.divider()
    
    # 技术路线说明
    with st.expander("🛠️ 技术路线（给老师展示）"):
        st.markdown("""
        ### 📊 多源数据融合方案
        
        | 数据类型 | 当前能力 | 生产方案 |
        |:---|:---|:---|
        | **结构化数据** (SQL数据库) | ✅ 已实现 - 自然语言转SQL | 覆盖卡口、线圈、信号机数据 |
        | **事故报告文本** | ✅ 已实现 - 关键词检索 | 向量数据库 + RAG语义检索 |
        | **交通视频** | 🔄 规划中 | CLIP多模态模型 + 向量检索 |
        | **政策法规** | ✅ 已实现 - 文档检索 | 知识图谱 + 智能问答 |
        | **互联网路况** | 🔄 规划中 | API接入 + 实时分析 |
        
        ### 🧠 核心技术栈
        - **大模型**: 支持接入DeepSeek、Qwen等
        - **向量数据库**: Chroma / Milvus
        - **RAG框架**: LangChain / LlamaIndex
        - **多模态**: CLIP / 视觉大模型
        """)

# ============ 页脚 ============
st.divider()
st.caption(f"""
**🚦 交通数据智能分析平台 v2.0** | 
支持多轮对话 · 结构化SQL查询 · 非结构化文档检索 · 智能报告生成 | 
数据更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}
""")
