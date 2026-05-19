import json

with open("weibo_hot_2026-05-11.json", "r", encoding="utf-8") as f:
    data = json.load(f)

latest = data[-1]   # 取最后一条记录
print("最新抓取时间:", latest.get("timestamp"))
print("热搜总数:", latest.get("total"))

# 打印前 5 条热搜的“第一条博文”情况
for item in latest["hot_list"][:5]:
    word = item.get("热搜词")
    post = item.get("第一条博文")
    if post:
        print(f"\n【{word}】")
        print(f"  博主: {post.get('博主名字')}")
        print(f"  头像: {post.get('头像')[:60]}...")
        print(f"  内容: {post.get('文章内容')[:80]}...")
    else:
        print(f"\n【{word}】 → 第一条博文: null（未抓到）")