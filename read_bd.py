import pandas as pd
import sqlite3
import os

DB_FILE = "weibo_hot_data.db"
EXPORT_FILE = "微博热搜完美排版导出.xlsx"


def view_and_export_data():
    print("🔗 正在连接到数据库，准备提取数据...\n")

    if not os.path.exists(DB_FILE):
        print(f"❌ 致命错误：找不到数据库文件 '{DB_FILE}'。")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        query = "SELECT * FROM hot_search ORDER BY id DESC"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("⚠️ 数据库为空。")
            return

        df['avatar_url'] = df['avatar_url'].apply(
            lambda x: f"https:{x}" if isinstance(x, str) and x.startswith('//') else x
        )

        df['avatar_url'] = df['avatar_url'].replace('', '无头像')


        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        pd.set_option('display.unicode.ambiguous_as_wide', True)
        pd.set_option('display.unicode.east_asian_width', True)

        print(f"✅ 成功提取 {len(df)} 条记录！预览如下：")
        print("-" * 90)
        print(df[['timestamp', 'rank', 'title', 'label', 'author', 'avatar_url']].head(5))
        print("-" * 90)

        df.to_excel(EXPORT_FILE, index=False, engine='openpyxl')

        print(f"\n🎉 完美收工！")
        print(f"数据已升级为原生 Excel 格式：【{EXPORT_FILE}】")
        print("👉 现在去打开这个 .xlsx 文件，里面的链接应该都是蓝色、可以直接点击的了！")

    except Exception as e:
        print(f"❌ 在处理数据时发生意外波动: {e}")


if __name__ == "__main__":
    view_and_export_data()