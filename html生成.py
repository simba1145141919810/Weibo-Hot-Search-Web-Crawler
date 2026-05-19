import pandas as pd
import sqlite3
import os
from urllib.parse import quote

DB_FILE = "weibo_hot_data.db"
HTML_FILE = "微博热搜可视化看板.html"


def format_avatar(avatar_url, title):
    weibo_search_url = f"https://s.weibo.com/weibo?q={quote(title)}"

    if not avatar_url or not isinstance(avatar_url, str) or avatar_url.strip() == "":
        img_tag = '<span style="color:#bbb; font-size:12px;">无图</span>'
    else:
        raw_url = avatar_url.strip()
        if raw_url.startswith('//'):
            raw_url = 'https:' + raw_url

        img_tag = f'''<img src="{raw_url}" width="45" height="45" 
             style="border-radius:50%; object-fit: cover; border: 1px solid #eee;"
             referrerpolicy="no-referrer"
             onerror="this.src='https://via.placeholder.com/45?text=博主'; this.style.opacity=0.6;">'''

    return f'<a href="{weibo_search_url}" target="_blank" title="点击去微博看【{title}】的原帖">{img_tag}</a>'


def format_title(title):
    weibo_search_url = f"https://s.weibo.com/weibo?q={quote(title)}"
    return f'<a href="{weibo_search_url}" target="_blank" style="color:#1da1f2; text-decoration:none; font-weight:bold;">{title}</a>'


def generate_html_dashboard():
    print("🔗 正在读取数据库数据...")
    if not os.path.exists(DB_FILE):
        print(f"❌ 找不到数据库文件 '{DB_FILE}'")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        query = "SELECT timestamp, rank, title, label, author, avatar_url, summary FROM hot_search ORDER BY id DESC LIMIT 100"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("⚠️ 数据库为空。")
            return

        df['avatar_url'] = df.apply(lambda row: format_avatar(row['avatar_url'], row['title']), axis=1)
        df['title'] = df['title'].apply(format_title)

        df.columns = ['抓取时间', '排名', '热搜标题(点击吃瓜)', '标签', '博主', '头像(点击吃瓜)', '博文摘要']

        html_table = df.to_html(escape=False, index=False, classes='weibo-table')

        html_content = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="utf-8">
            <meta name="referrer" content="no-referrer">
            <title>微博热搜深度监控看板</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; 
                       background-color: #f4f6f8; margin: 0; padding: 30px; }}
                .container {{ max-width: 1300px; margin: 0 auto; background: white; padding: 30px; 
                             border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.05); }}
                h2 {{ color: #1da1f2; margin-top: 0; padding-bottom: 15px; border-bottom: 2px solid #f0f2f5; }}
                .weibo-table {{ border-collapse: collapse; width: 100%; margin-top: 20px; table-layout: fixed; }}
                .weibo-table th {{ background-color: #f8f9fa; color: #495057; text-align: left; padding: 15px; 
                                  border-bottom: 2px solid #dee2e6; font-size: 15px; }}
                .weibo-table td {{ padding: 15px; border-bottom: 1px solid #f0f2f5; font-size: 14px; 
                                  word-wrap: break-word; vertical-align: middle; line-height: 1.5; color: #333; }}
                .weibo-table tr:hover {{ background-color: #f1f8ff; transition: all 0.2s ease; }}

                /* 精准控制每一列的宽度，排版更美观 */
                th:nth-child(1) {{ width: 140px; color: #888; }} /* 时间 */
                th:nth-child(2) {{ width: 40px; text-align: center; font-weight: 900; color: #ff5722; }}  /* 排名 */
                th:nth-child(3) {{ width: 220px; }} /* 标题 */
                th:nth-child(4) {{ width: 50px; text-align: center; }}  /* 标签 */
                th:nth-child(5) {{ width: 100px; color: #666; }} /* 博主 */
                th:nth-child(6) {{ width: 80px; text-align: center; }}  /* 头像 */
            </style>
        </head>
        <body>
            <div class="container">
                <h2>📈 全网热点实时情报舱</h2>
                <p style="color: #888; font-size: 14px;">已自动屏蔽死链。点击 <b>蓝色标题</b> 或 <b>博主头像</b> 即可无缝直飞微博吃瓜现场。</p>
                {html_table}
            </div>
        </body>
        </html>
        """

        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"🎉 终极版看板生成完毕！已彻底解决 403 阻断问题。")

    except Exception as e:
        print(f"❌ 生成看板失败: {e}")


if __name__ == "__main__":
    generate_html_dashboard()