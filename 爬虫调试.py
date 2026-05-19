import sqlite3
import time
import os
import random
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from urllib.parse import quote
import httpx
from playwright.sync_api import sync_playwright

import os


os.environ["http_proxy"] = "http://127.0.0.1:1082"
os.environ["https_proxy"] = "http://127.0.0.1:1082"


HOT_SEARCH_URL = "https://weibo.com/ajax/statuses/hot_band"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://weibo.com/",
}
INTERVAL = 1800
DB_FILE = "weibo_hot_data.db"


def init_db():
    """初始化数据库和表结构"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hot_search (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            rank INTEGER,
            title TEXT,
            label TEXT,
            author TEXT,
            avatar_url TEXT,
            summary TEXT
        )
    ''')
    conn.commit()
    conn.close()


# 确保程序一启动就建好表
init_db()


# --- 模块1：子页面深度抓取 ---
def get_first_post_mobile(page, word):
    if not word: return {"博主": "空关键词", "头像": "", "博文摘要": "暂无摘要"}
    encoded_word = quote(word)
    url = f"https://m.weibo.cn/search?containerid=100103type%3D1%26q%3D{encoded_word}"

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        try:
            page.wait_for_selector('.weibo-text', timeout=6000)
        except Exception:
            error_img = f"error_{word[:5]}.png"  # 限制文件名长度防止系统报错
            page.screenshot(path=error_img)
            print(f"      [警告] 页面未正常加载卡片，已截图保存至: {error_img}")
            return {"博主": "页面加载异常", "头像": "", "博文摘要": "请查看截图"}

        card = page.locator('.card-wrap, .card-main').first
        if card.count() > 0:
            author_name = card.locator('.name, .m-text-cut').first.inner_text().strip()
            avatar_loc = card.locator('.avatar img, .m-img-box img').first
            avatar_url = avatar_loc.get_attribute('src') if avatar_loc.count() > 0 else ""
            summary = card.locator('.weibo-text').first.inner_text().strip()
            summary = summary.replace('\n', ' ')[:100]

            return {"博主": author_name, "头像": avatar_url, "博文摘要": summary}

    except Exception as e:
        print(f"      [错误] 抓取页面 '{word}' 时发生网络/渲染波动: {e}")

    return {"博主": "解析失败", "头像": "", "博文摘要": "暂无摘要"}


# --- 模块2：数据可视化分析 ---
def generate_trend_chart():
    """读取 SQLite 数据并生成不同分类的数量曲线图"""
    if not os.path.exists(DB_FILE):
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        today_str = datetime.now().strftime('%Y-%m-%d')

        query = f"""
            SELECT timestamp AS 时间, label AS 标签 
            FROM hot_search 
            WHERE timestamp LIKE '{today_str}%'
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return

        df['标签'] = df['标签'].replace('', '常规')
        df['时间'] = pd.to_datetime(df['时间'])

        report = df.pivot_table(index='时间', columns='标签', aggfunc='size', fill_value=0)

        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

        plt.figure(figsize=(12, 6))
        report.plot(kind='line', marker='o', ax=plt.gca())

        plt.title(f"微博热搜分类趋势统计 ({today_str})")
        plt.xlabel("抓取时间点")
        plt.ylabel("热搜条数")
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend(title="热搜类型", bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()

        plt.savefig("hot_search_trend_chart.png")
        plt.close()
        print(f"📈 统计图表已基于 SQLite 数据更新: hot_search_trend_chart.png")

    except Exception as e:
        print(f"绘图异常调试信息: {e}")


# --- 模块3：核心爬取流程 ---
def run_task():
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{current_time}] 启动自动化爬取流...")

    # 1. 抓取基础数据
    try:
        with httpx.Client(headers=HEADERS, timeout=15) as client:
            resp = client.get(HOT_SEARCH_URL)
            hot_data = resp.json().get("data", {}).get("band_list", [])[:50]
            hot_data = [item for item in hot_data if item.get("word")]

            print(f"成功获取 {len(hot_data)} 条热搜词")
            if len(hot_data) == 0: return
    except Exception as e:
        print(f"热搜接口访问失败: {e}")
        return

    results = []
    # 2. 抓取深度信息
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        for idx, item in enumerate(hot_data, 1):
            # 【防崩溃护城河】：捕获循环内的任何致命异常
            try:
                word = item.get("word", "")
                label = item.get("label_name", "常规")
                print(f"  [{idx}/{len(hot_data)}] 正在解析: {word} ({label})")

                post_info = get_first_post_mobile(page, word)
                results.append({
                    "rank": idx,
                    "title": word,
                    "label": label,
                    "author": post_info["博主"],
                    "avatar": post_info["头像"],
                    "summary": post_info["博文摘要"]
                })
                time.sleep(random.uniform(0.5, 1.5))

            except Exception as e:
                # 使用 continue 直接跳过报错的词条，保证爬虫不死
                print(f"      [致命错误] 处理 '{item.get('word', '未知词条')}' 时崩溃，已安全跳过。报错内容: {e}")
                continue

        browser.close()

    # 3. 将结果持久化到 SQLite 数据库
    try:
        if results:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            insert_query = '''
                INSERT INTO hot_search (timestamp, rank, title, label, author, avatar_url, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''

            data_to_insert = [
                (current_time, r["rank"], r["title"], r["label"], r["author"], r["avatar"], r["summary"])
                for r in results
            ]

            cursor.executemany(insert_query, data_to_insert)
            conn.commit()
            conn.close()
            print(f"💾 {len(results)} 条记录已安全写入 SQLite 数据库")
        else:
            print("⚠️ 本轮未抓取到有效深度数据，跳过数据库写入。")

    except Exception as db_e:
        print(f"数据库写入异常: {db_e}")

    # 自动执行可视化分析
    generate_trend_chart()


if __name__ == "__main__":
    print("🚀 资深程序员模式：微博热搜坚不可摧版监控系统已启动")
    while True:
        try:
            run_task()
        except Exception as main_e:
            print(f"系统运行发生不可预知的全局波动: {main_e}")

        print(f"\n等待 {INTERVAL / 60} 分钟后进行下一轮监控...")
        time.sleep(INTERVAL)