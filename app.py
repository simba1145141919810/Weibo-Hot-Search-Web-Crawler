import os
import sqlite3
import time
import random
import json
import re
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from urllib.parse import quote
import httpx
from openai import OpenAI
import streamlit as st
from bs4 import BeautifulSoup

SNAPSHOT_DIR = "history_snapshots"
if not os.path.exists(SNAPSHOT_DIR):
    os.makedirs(SNAPSHOT_DIR)

WEIBO_COOKIE = st.secrets["WEIBO_COOKIE"]

HOT_SEARCH_URL = "https://weibo.com/ajax/statuses/hot_band"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://weibo.com/",
    "Cookie": WEIBO_COOKIE
}
DB_FILE = "weibo_hot_data.db"


def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        'CREATE TABLE IF NOT EXISTS hot_search (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, rank INTEGER, title TEXT, label TEXT, author TEXT, avatar_url TEXT, summary TEXT)')
    try:
        cursor.execute('ALTER TABLE hot_search ADD COLUMN ai_category TEXT')
    except:
        pass
    conn.commit()
    conn.close()


import json


def get_post_detail_api(word):
    if not word: return {"博主": "空", "头像": "", "博文摘要": "暂无"}

    url = f"https://s.weibo.com/weibo?q={quote(word)}"

    pc_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Cookie": WEIBO_COOKIE,
        "Referer": "https://s.weibo.com/top/summary"
    }

    try:
        resp = httpx.get(url, headers=pc_headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'lxml')

        cards = soup.find_all('div', class_='card-wrap')

        for card in cards:
            if 'mid' not in card.attrs:
                continue

            name_tag = card.find('a', class_='name')
            name = name_tag.text.strip() if name_tag else "未知博主"

            avatar = ""
            avatar_div = card.find('div', class_='avator')
            if avatar_div:
                img_tag = avatar_div.find('img')
                if img_tag and 'src' in img_tag.attrs:
                    avatar = img_tag['src']
                    if avatar.startswith('//'):
                        avatar = "https:" + avatar

            txt_tag = card.find('p', class_='txt', attrs={'node-type': 'feed_list_content'})
            if not txt_tag:
                txt_tag = card.find('p', class_='txt')

            if txt_tag:
                txt = txt_tag.get_text(separator=' ', strip=True)
                txt = txt.replace('收起全文 d', '').strip()[:100]  # 去掉展开全文带来的尾巴
            else:
                txt = "未能提取到正文"

            return {"博主": name, "头像": avatar, "博文摘要": txt}

    except Exception as e:
        print(f"抓取热搜 [{word}] 详情失败: 错误信息 -> {e}")

    return {"博主": "页面无动态", "头像": "", "博文摘要": "微博未加载内容"}


def classify_by_ai_batch(items, client, model_name):
    prompt_text = (
        "你是一个严谨的数据分析师。请为以下50条微博热搜进行分类。\n"
        "可选分类严格限制为以下9个：社会, 文娱, 体育, 财经, 科技, 军事, 国际, 游戏, 其他。\n"
        "【极其重要】：请只返回一个合法的 JSON 字典，不要输出任何多余的解释文字。键为热搜的排名(字符串格式)，值为你判断的分类结果。\n"
        "格式示例：{\"1\": \"社会\", \"2\": \"科技\", \"3\": \"文娱\"}\n\n"
        "待分类热搜数据如下：\n"
    )

    for item in items:
        prompt_text += f"排名:{item['rank']} | 标题:{item['title']} | 摘要:{item['summary'][:60]}\n"

    for _ in range(3):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.1,
                timeout=45.0
            )

            content = response.choices[0].message.content.strip()

            try:
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                return json.loads(content)

            except json.JSONDecodeError as je:
                st.error(f"❌ AI 返回的数据格式不对，无法解析为 JSON: {je}")
                st.code(content)
                return {}

        except Exception as e:
            st.error(f"❌ AI 接口调用彻底失败: {e}")
            time.sleep(2)

    return {}


def make_excel_and_html(results, current_time_str, filename_time_str):
    if not results: return
    df = pd.DataFrame(results)
    df_excel = df.copy()
    df_excel['直达链接'] = df_excel['title'].apply(lambda x: f"https://s.weibo.com/weibo?q={quote(x)}")
    excel_columns_map = {'rank': '排名', 'title': '热搜标题', 'ai_category': 'AI智能分类', 'author': '博主',
                         'summary': '摘要', '直达链接': '链接'}
    df_excel = df_excel[list(excel_columns_map.keys())].rename(columns=excel_columns_map)
    excel_path = f"{SNAPSHOT_DIR}/快照_{filename_time_str}.xlsx"
    df_excel.to_excel(excel_path, index=False, engine='openpyxl')
    return excel_path


def start_one_round(progress_bar, status_text, client, model_name):
    now = datetime.now()
    cur_time = now.strftime('%Y-%m-%d %H:%M:%S')
    file_time = now.strftime('%Y%m%d_%H%M%S')

    status_text.text("🚀 正在获取微博官方榜单...")
    try:
        resp = httpx.get(HOT_SEARCH_URL, headers=HEADERS, timeout=10)
        items = resp.json().get("data", {}).get("band_list", [])
        valid_items = [i for i in items if i.get("word")][:50]
    except Exception as e:
        st.error(f"❌ 访问微博接口失败: {e}")
        return None, None

    final_results = []
    status_text.text("🕷️ 正在通过底层 API 高速抓取详情...")

    for idx, item in enumerate(valid_items, 1):
        word = item.get("word", "")
        detail = get_post_detail_api(word)

        final_results.append({
            "rank": idx, "title": word, "label": item.get("label_name", "常规"),
            "author": detail["博主"], "avatar": detail["头像"], "summary": detail["博文摘要"],
            "ai_category": "处理中..."
        })
        progress_bar.progress(idx / 50, text=f"正在极速抓取: {word}")
        time.sleep(random.uniform(1.3, 3.8))


    status_text.text("🧠 正在呼叫 AI 进行全局语义分类 (单次全量处理)...")
    progress_bar.progress(0.99, text="等待 AI 批量处理中，这可能需要十多秒，请稍候...")

    batch_items = [{"rank": r["rank"], "title": r["title"], "summary": r["summary"]} for r in final_results]
    category_mapping = classify_by_ai_batch(batch_items, client, model_name)
    for r in final_results:
        r["ai_category"] = category_mapping.get(str(r["rank"]), "其他")

    status_text.text("🗄️ 正在同步数据库与生成备份...")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        data_in = [
            (cur_time, r["rank"], r["title"], r["label"], r["author"], r["avatar"], r["summary"], r["ai_category"]) for
            r in final_results]
        cursor.executemany(
            'INSERT INTO hot_search (timestamp, rank, title, label, author, avatar_url, summary, ai_category) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            data_in)
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"存数据库异常: {e}")

    try:
        make_excel_and_html(final_results, cur_time, file_time)
    except Exception as e:
        st.error(f"⚠️ 写入 Excel 备份失败 (不影响网页展示): {e}")

    status_text.text("✅ 本轮分析完成！")
    return final_results, cur_time


st.set_page_config(page_title="微博热搜 AI 洞察", page_icon="📈", layout="wide")
init_database()

st.sidebar.markdown(
    """
    <div style='border-left: 4px solid #4169E1; padding-left: 12px; margin-bottom: 20px;'>
        <h3 style='color: #4169E1; margin:0; font-weight: 500;'>Insight Engine</h3>
        <p style='color: #87CEEB; font-size: 0.85em; margin-top: 4px; font-style: italic;'>Universal AI Agent</p>
    </div>
    """,
    unsafe_allow_html=True
)

user_api_key = st.sidebar.text_input("1. API Key", type="password", help="填入您选择的大模型供应商的 API 密钥。")
user_base_url = st.sidebar.text_input("2. API Base URL", value="https://api.x.ai/v1", help="例如：OpenAI 使用 https://api.openai.com/v1，DeepSeek 使用 https://api.deepseek.com")
user_model_name = st.sidebar.text_input("3. 模型名称 (Model Name)", value="grok-beta", help="例如：gpt-4o, deepseek-chat, grok-2-latest")

st.sidebar.markdown("<p style='font-size: 0.8em; color: #666;'>*核心提示：若留空Key，系统将默认尝试读取云端配置文件中的硬编码配额。</p>", unsafe_allow_html=True)

API_KEY = user_api_key if user_api_key else st.secrets.get("API_KEY", "")
BASE_URL = user_base_url if user_base_url else "https://api.x.ai/v1"
MODEL_NAME = user_model_name if user_model_name else "grok-beta"

if API_KEY:
    ai_client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
else:
    ai_client = None

# --- 主界面 UI ---
st.title("📈 微博热搜 AI 实时洞察平台")
st.markdown("基于大语言模型与自动化爬虫的社情民意监控看板。点击下方按钮即可触发实时分析。")

col1, col2 = st.columns([1, 4])
with col1:
    run_btn = st.button("🚀 立即拉取并分析", type="primary", use_container_width=True)

if run_btn:
    if not ai_client:
        st.error("⚠️ 核心驱动缺失：请在左侧边栏配置有效的 API Key 以启动 AI 分类引擎。")
        st.stop()

    progress_bar = st.progress(0, text="初始化中...")
    status_text = st.empty()

    results, cur_time = start_one_round(progress_bar, status_text, ai_client, MODEL_NAME)

    if results:
        df = pd.DataFrame(results)

        st.subheader(f"📊 数据看版 ({cur_time})")
        display_df = df[['rank', 'title', 'ai_category', 'author', 'summary']].copy()
        display_df.columns = ['排名', '热搜标题', 'AI分类', '首条博主', '摘要']
        st.dataframe(display_df, use_container_width=True, height=400)

        st.subheader("📉 数据可视化")
        tab1, tab2, tab3 = st.tabs(["当次分类分布", "历史总计分布", "热度趋势折线"])

        with tab1:
            st.markdown(f"**微博热搜当次智能分类统计 ({cur_time})**")
            valid_df = df[~df['ai_category'].isin(['处理中...', '分类超时', '暂无'])]
            if not valid_df.empty:
                category_counts = valid_df['ai_category'].value_counts()
                st.bar_chart(category_counts, color="#4a68c4")

        with tab2:
            st.markdown(f"**微博热搜历史全局分类总计 (截至 {cur_time})**")
            try:
                conn = sqlite3.connect(DB_FILE)
                history_df = pd.read_sql_query("SELECT ai_category FROM hot_search", conn)
                conn.close()
                history_df = history_df[~history_df['ai_category'].isin(['处理中...', '分类超时', '暂无'])]
                if not history_df.empty:
                    history_counts = history_df['ai_category'].value_counts()
                    st.bar_chart(history_counts, color="#e67e22")
            except:
                st.info("暂无历史数据")

        with tab3:
            st.markdown(f"**微博热搜各分类热度趋势变化 ({cur_time})**")
            try:
                conn = sqlite3.connect(DB_FILE)
                trend_data = pd.read_sql_query("SELECT timestamp, ai_category FROM hot_search", conn)
                conn.close()
                trend_data = trend_data[~trend_data['ai_category'].isin(['处理中...', '分类超时', '暂无'])]
                if not trend_data.empty:
                    trend_pivot = trend_data.groupby(['timestamp', 'ai_category']).size().unstack(fill_value=0)
                    st.line_chart(trend_pivot)
            except:
                st.info("历史数据不足，无法生成趋势图")