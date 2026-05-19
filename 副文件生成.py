import os
import sqlite3
import time
import random
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from urllib.parse import quote
import httpx
from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv

SNAPSHOT_DIR = "history_snapshots"
if not os.path.exists(SNAPSHOT_DIR):
    os.makedirs(SNAPSHOT_DIR)

load_dotenv("API_KEY.env")

API_KEY = os.getenv("API_KEY")
WEIBO_COOKIE = os.getenv("WEIBO_COOKIE")

if not API_KEY:
    print("❌ 致命错误：找不到 API_KEY！请检查环境变量文件。")
    exit()
if not WEIBO_COOKIE:
    print("❌ 致命错误：找不到微博 Cookie！请检查环境变量文件。")
    exit()

custom_http_client = httpx.Client(
    proxy="http://127.0.0.1:1082"
)

ai_client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.x.ai/v1"
)

HOT_SEARCH_URL = "https://weibo.com/ajax/statuses/hot_band"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://weibo.com/",
    "Cookie": WEIBO_COOKIE
}
DB_FILE = "weibo_hot_data.db"
INTERVAL = 1800


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


def classify_by_ai(title, summary):
    prompt_text = f"你是一个严谨的数据分析师。请将该热搜分类（只能输出：社会, 文娱, 体育, 财经, 科技, 军事, 国际, 游戏, 其他）。如果不确定，请输出“其他”：\n标题：{title}\n摘要：{summary}"
    try:
        response = ai_client.chat.completions.create(
            model="grok-4.20-reasoning",
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.1,
            timeout=10.0  # 缩短超时时间，避免卡死
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"      [🚨 AI无响应/报错] 跳过分类，原因: {e}")
        return "分类超时"


def get_post_detail(page, word):
    if not word: return {"博主": "空", "头像": "", "博文摘要": "暂无"}
    url = f"https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D{quote(word)}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        try:
            page.wait_for_selector('.weibo-text', timeout=3000)
        except:
            return {"博主": "页面无动态", "头像": "", "博文摘要": "微博未加载内容"}

        card = page.locator('.card-wrap, .card-main').first
        if card.count() > 0:
            name = card.locator('.name, .m-text-cut').first.inner_text().strip()
            avatar = card.locator('.avatar img, .m-img-box img').first
            avatar_url = avatar.get_attribute('src') if avatar.count() > 0 else ""
            txt = card.locator('.weibo-text').first.inner_text().strip().replace('\n', ' ')[:100]
            return {"博主": name, "头像": avatar_url, "博文摘要": txt}
    except:
        pass
    return {"博主": "解析失败", "头像": "", "博文摘要": "暂无"}


def make_bar_chart(df, current_time_str, filename_time_str):
    if df.empty or 'ai_category' not in df.columns: return
    category_counts = df['ai_category'].value_counts()

    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    plt.figure(figsize=(10, 6))

    bars = plt.bar(category_counts.index, category_counts.values, color='#4a68c4', edgecolor='none', alpha=0.8)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, yval + 0.5, int(yval), ha='center', va='bottom', color='#555555')

    plt.title(f"微博热搜智能分类统计 ({current_time_str})", fontsize=16, color='#333333', pad=15)
    plt.xlabel("AI 智能分类", fontsize=12, labelpad=10)
    plt.ylabel("热搜数量", fontsize=12, labelpad=10)
    plt.grid(axis='y', linestyle='--', alpha=0.3)

    plt.gca().spines['top'].set_visible(False)
    plt.gca().spines['right'].set_visible(False)

    plt.tight_layout()
    chart_path = f"{SNAPSHOT_DIR}/分类柱状图_{filename_time_str}.png"
    plt.savefig(chart_path, dpi=150, transparent=False)
    plt.close()
    print(f"📊 柱状图已生成: {chart_path}")


def make_line_chart(current_time_str, filename_time_str):
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT timestamp, ai_category FROM hot_search", conn)
        conn.close()

        if df.empty: return

        # 过滤掉未分类的数据
        df = df[~df['ai_category'].isin(['处理中...', '分类超时', '暂无'])]
        if df.empty: return

        # 按时间和分类进行统计
        trend_df = df.groupby(['timestamp', 'ai_category']).size().unstack(fill_value=0)

        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
        plt.figure(figsize=(12, 6))

        for category in trend_df.columns:
            plt.plot(trend_df.index, trend_df[category], marker='o', linewidth=2, label=category)

        plt.title(f"微博热搜各分类热度趋势变化 ({current_time_str})", fontsize=16, color='#333333', pad=15)
        plt.xlabel("抓取时间段", fontsize=12, labelpad=10)
        plt.ylabel("热搜上榜数量", fontsize=12, labelpad=10)
        plt.xticks(rotation=45, ha='right')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(axis='y', linestyle='--', alpha=0.3)
        plt.gca().spines['top'].set_visible(False)
        plt.gca().spines['right'].set_visible(False)

        plt.tight_layout()
        chart_path = f"{SNAPSHOT_DIR}/分类趋势折线图_{filename_time_str}.png"
        plt.savefig(chart_path, dpi=150, transparent=False)
        plt.close()
        print(f"📈 折线图已生成: {chart_path}")
    except Exception as e:
        print(f"📉 生成折线图失败: {e}")


def make_excel_and_html(results, current_time_str, filename_time_str):
    if not results: return

    df = pd.DataFrame(results)
    df_excel = df.copy()

    df_excel['直达链接'] = df_excel['title'].apply(lambda x: f"https://s.weibo.com/weibo?q={quote(x)}")
    df_excel['avatar'] = df_excel['avatar'].apply(
        lambda x: 'https:' + x if type(x) == str and x.startswith('//') else x)

    excel_columns_map = {
        'rank': '排名',
        'title': '热搜标题',
        'ai_category': 'AI智能分类',
        'author': '首条文章博主',
        'summary': '第一篇文章摘要',
        '直达链接': '点击直达链接',
        'avatar': '博主头像链接'
    }
    df_excel = df_excel[list(excel_columns_map.keys())].rename(columns=excel_columns_map)

    excel_path = f"{SNAPSHOT_DIR}/热搜快照_{filename_time_str}.xlsx"
    df_excel.to_excel(excel_path, index=False, engine='openpyxl')
    print(f"📑 Excel 数据表已更新: {excel_path}")

    df_html = df.copy()

    def create_html_link(title):
        url = f"https://s.weibo.com/weibo?q={quote(title)}"
        return f'<a href="{url}" target="_blank">{title}</a>'

    df_html['title'] = df_html['title'].apply(create_html_link)

    html_columns_map = {
        'rank': '排名',
        'title': '热搜标题 (点击查看)',
        'ai_category': 'AI分类',
        'author': '热门博主',
        'summary': '热门内容摘要'
    }
    df_html = df_html[list(html_columns_map.keys())].rename(columns=html_columns_map)

    html_table_code = df_html.to_html(escape=False, index=False, classes='modern-table')

    html_content = f"""<!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <title>微博热搜快照 - {current_time_str}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background: linear-gradient(135deg, #eef2f9 0%, #e0e8f5 100%);
                padding: 40px 20px;
                color: #2c3e50;
                margin: 0;
            }}
            .container {{
                max-width: 1200px;
                margin: auto;
                background: rgba(255, 255, 255, 0.65);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 16px;
                padding: 30px 40px;
                box-shadow: 0 10px 30px rgba(74, 104, 196, 0.08);
            }}
            .header-info {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 25px;
            }}
            h2 {{ color: #4a68c4; font-weight: 600; margin: 0; }}
            .time-badge {{
                background: rgba(74, 104, 196, 0.1);
                color: #4a68c4;
                padding: 6px 12px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 500;
            }}
            .modern-table {{
                border-collapse: separate;
                border-spacing: 0;
                width: 100%;
                text-align: left;
                background: rgba(255, 255, 255, 0.5);
                border-radius: 12px;
                overflow: hidden;
            }}
            .modern-table th, .modern-table td {{
                padding: 14px 16px;
                border-bottom: 1px solid rgba(74, 104, 196, 0.06);
            }}
            .modern-table th {{
                background: rgba(74, 104, 196, 0.05);
                color: #4a68c4;
                font-weight: 600;
                text-transform: uppercase;
                font-size: 13px;
                letter-spacing: 0.5px;
            }}
            .modern-table tr:last-child td {{ border-bottom: none; }}
            .modern-table tr:hover td {{ background: rgba(255, 255, 255, 0.8); }}
            a {{ color: #5a7bd6; text-decoration: none; font-weight: 500; transition: color 0.2s; }}
            a:hover {{ color: #3753a8; text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-info">
                <h2>📊 智能热搜分析洞察</h2>
                <div class="time-badge">采集时间：{current_time_str}</div>
            </div>
            {html_table_code}
        </div>
    </body>
    </html>"""

    html_path = f"{SNAPSHOT_DIR}/热搜看板_{filename_time_str}.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"🌐 HTML 看板已更新: {html_path}")


def start_one_round():
    now = datetime.now()
    cur_time = now.strftime('%Y-%m-%d %H:%M:%S')
    file_time = now.strftime('%Y%m%d_%H%M%S')
    print(f"\n[{cur_time}] 🚀 阶段 1：启动纯净版高速自动化爬取...")

    try:
        resp = httpx.get(HOT_SEARCH_URL, headers=HEADERS, timeout=10)
        items = resp.json().get("data", {}).get("band_list", [])
        if not items:
            print("❌ 获取到的榜单为空！可能是 Cookie 失效。")
            return
        valid_items = [i for i in items if i.get("word")][:50]
    except Exception as e:
        print(f"❌ 访问微博接口失败: {e}")
        return

    final_results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])

        for idx, item in enumerate(valid_items, 1):
            word = item.get("word", "")
            print(f"  [{idx}/50] 正在极速抓取: {word}")
            detail = get_post_detail(page, word)

            final_results.append({
                "rank": idx,
                "title": word,
                "label": item.get("label_name", "常规"),
                "author": detail["博主"],
                "avatar": detail["头像"],
                "summary": detail["博文摘要"],
                "ai_category": "处理中..."  # 初始状态设为处理中
            })
            time.sleep(random.uniform(1.3, 3.8))  # 稍微加快了爬取间隔
        browser.close()

    if not final_results:
        return

    # 【核心改动 1】：无论 AI 结果如何，爬完第一时间先生成 Excel 和 HTML 保底
    print(f"\n[{cur_time}] 💾 阶段 2：输出基础数据，保证本地有档可查...")
    make_excel_and_html(final_results, cur_time, file_time)

    # 【核心改动 2】：脱离浏览器环境，集中进行 AI 文本分类
    print(f"\n[{cur_time}] 🧠 阶段 3：开始集中进行 AI 语义分类...")
    for idx, r in enumerate(final_results, 1):
        print(f"  [{idx}/50] AI 正在分类: {r['title']}")
        r["ai_category"] = classify_by_ai(r["title"], r["summary"])
        time.sleep(0.1)  # 保护 API 速率

    # 阶段 4：将含有 AI 分类的最终数据存入 SQLite 数据库
    print(f"\n[{cur_time}] 🗄️ 阶段 4：同步数据至 SQLite...")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        data_in = [
            (cur_time, r["rank"], r["title"], r["label"], r["author"], r["avatar"], r["summary"], r["ai_category"])
            for r in final_results]
        cursor.executemany(
            'INSERT INTO hot_search (timestamp, rank, title, label, author, avatar_url, summary, ai_category) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            data_in)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"存数据库异常: {e}")

    # 阶段 5：更新覆盖本地的 Excel 和 HTML，使其具备分类信息；并作图
    print(f"\n[{cur_time}] 🎨 阶段 5：更新本地看板并生成数据图表...")
    df_for_files = pd.DataFrame(final_results)

    make_excel_and_html(final_results, cur_time, file_time)  # 覆盖之前的保底文件
    make_bar_chart(df_for_files, cur_time, file_time)
    make_line_chart(cur_time, file_time)  # 绘制历史趋势折线图


if __name__ == "__main__":
    init_database()
    print("🌟 数据挖掘、AI分析与自动化制表系统已就绪！")

    while True:
        try:
            start_one_round()
        except Exception as e:
            print(f"全局异常报错: {e}")

        print(f"\n本轮结束，程序休息 {INTERVAL / 60} 分钟...")
        time.sleep(INTERVAL)