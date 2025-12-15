# 导入工具（小白不用动）
import feedparser
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import html
import re

# ---------------------- 方案一专用：读取GitHub环境变量（关键！） ----------------------
# 从GitHub Actions的环境变量中读取Secrets的信息，替换空变量
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
RECEIVER_EMAILS = os.getenv("RECEIVER_EMAILS", "")
# ------------------------------------------------------------------

# 数据源配置（路透社+彭博社，小白不用动）
RSS_SOURCES = [
    ("https://reutersnew.buzzing.cc/feed.xml", "路透社"),
    ("https://bloombergnew.buzzing.cc/feed.xml", "彭博社")
]

# 邮件颜色配置（橙色时间、红色路透社、蓝色彭博社、绿色🔗，小白不用动）
COLORS = {
    "time": "#F97316",       # 时间：橙色
    "reuters": "#E63946",    # 路透社：红色
    "bloomberg": "#1D4ED8",  # 彭博社：蓝色
    "link": "#16A34A",       # 链接符号：绿色
    "title": "#2E4057"       # 主标题：深蓝色
}

# 防重复推送：读取已发过的资讯ID（小白不用动）
def get_pushed_ids():
    if not os.path.exists("pushed_ids.txt"):
        return set()
    with open("pushed_ids.txt", "r", encoding="utf-8") as f:
        return set(f.read().splitlines())

# 防重复推送：保存已发过的资讯ID（小白不用动）
def save_pushed_id(id):
    with open("pushed_ids.txt", "a", encoding="utf-8") as f:
        f.write(f"{id}\n")

# 发送邮件（Gmail发件+批量收件，小白不用动）
def send_email(subject, content, news_bj_date):
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 微软雅黑, Arial, sans-serif; line-height: 2.2; font-size: 15px; }}
            li {{ margin-bottom: 12px; list-style: none; padding-left: 8px; }}
            a {{ text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <h2 style="color:{COLORS['title']}; font-size:18px; margin-bottom:25px;">📩 最新资讯推送（{news_bj_date}）</h2>
        <ul style="padding-left:22px; margin:0;">
            {content}
        </ul>
    </body>
    </html>
    """
    msg = MIMEText(html_content, "html", "utf-8")
    msg["From"] = GMAIL_EMAIL  # 发件人：从环境变量读取
    msg["To"] = RECEIVER_EMAILS  # 收件人：从环境变量读取
    msg["Subject"] = subject  # 邮件标题：完整北京时间（年-月-日）

    try:
        # 连接Gmail服务器（固定参数，小白不用动）
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)  # 登录信息从环境变量读取
        smtp.sendmail(GMAIL_EMAIL, RECEIVER_EMAILS.split(","), msg.as_string())  # 批量发邮件
        smtp.quit()
        print("✅ 邮件推送成功！发件人：Gmail（方案一安全版）")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail登录失败！检查：1.Secrets里的邮箱/密码是否正确 2.环境变量是否读取成功")
    except Exception as e:
        print(f"❌ 推送失败：{e}")

# 提取资讯展示时间（分时保持原始，不转换，小白不用动）
def get_show_time(entry, content):
    try:
        content = html.unescape(content).replace("\n", "").replace("\r", "").replace("\t", "").strip()
        time_patterns = [
            r'>\s*(\d{2}:\d{2})\s*<',
            r'<time[^>]*>\s*(\d{2}:\d{2})\s*</time>',
            r'datetime="[^"]*T(\d{2}:\d{2}):\d{2}[^"]*"'
        ]
        for pattern in time_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        entry_time = entry.get("updated", entry.get("published", ""))
        if entry_time:
            time_obj = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
            return time_obj.strftime("%m-%d")
        return datetime.now().strftime("%m-%d")
    except:
        return datetime.now().strftime("%m-%d")

# 提取资讯UTC时间并转换为【完整北京时间】（戳+年-月-日，小白不用动）
def get_news_bj_info(entry):
    try:
        entry_time = entry.get("updated", entry.get("published", ""))
        if entry_time:
            utc_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
            bj_time = utc_time + timedelta(hours=8)  # UTC+8=北京时间
            return bj_time.timestamp(), bj_time.strftime("%Y-%m-%d")  # 返回完整日期
        current_bj = datetime.now()
        return current_bj.timestamp(), current_bj.strftime("%Y-%m-%d")
    except:
        current_bj = datetime.now()
        return current_bj.timestamp(), current_bj.strftime("%Y-%m-%d")

# 核心逻辑：两处日期显示完整北京时间（年-月-日），其余功能不变
def fetch_rss():
    pushed_ids = get_pushed_ids()
    all_news = []  # 存储：(北京时间戳, 来源, 展示时间, 标题, 链接, 资讯ID, 完整北京时间)
    source_counter = {"路透社": 0, "彭博社": 0}  # 分源计数（括号内用）
    global_counter = 0  # 全局计数（最前面的连续序号）

    # 抓取并筛选所有数据源的资讯（小白不用动）
    for rss_url, source in RSS_SOURCES:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                entry_id = entry.get("id", "").strip()
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                content = entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""

                # 筛选条件：未推送+有有效ID+有标题+有合法链接（小白不用动）
                if entry_id not in pushed_ids and entry_id and title and link.startswith(("http", "https")):
                    show_time = get_show_time(entry, content)
                    bj_timestamp, news_bj_date = get_news_bj_info(entry)
                    all_news.append((bj_timestamp, source, show_time, title, link, entry_id, news_bj_date))
                    save_pushed_id(entry_id)  # 标记为已推送，避免重复
        except Exception as e:
            print(f"⚠️ {source}资讯抓取出错：{e}（不影响其他数据源）")

    # 按北京时间戳倒序排序（最新资讯在前，小白不用动）
    all_news.sort(key=lambda x: -x[0])
    news_html_list = []  # 存储每条资讯的HTML代码

    # 确定两处标题的显示日期：优先最新资讯的完整北京时间（小白不用动）
    if all_news:
        display_bj_date = all_news[0][6]  # 最新资讯的完整北京时间（年-月-日）
    else:
        display_bj_date = datetime.now().strftime("%Y-%m-%d")  # 兜底：当前完整北京时间

    # 生成带双序号+🔗符号的资讯列表（小白不用动）
    for news in all_news:
        bj_timestamp, source, show_time, title, link, _, _ = news
        global_counter += 1  # 全局序号+1
        source_counter[source] += 1  # 分源序号+1
        source_seq = source_counter[source]

        # 内联样式：颜色逻辑不变（小白不用动）
        time_style = f"color:{COLORS['time']};font-weight:bold;"
        source_color = COLORS["reuters"] if source == "路透社" else COLORS["bloomberg"]
        source_style = f"color:{source_color};font-weight:bold;"
        link_style = f"color:{COLORS['link']};"

        # 🔗符号替换原文链接（逻辑不变，小白不用动）
        news_html = f"""
        <li>
            {global_counter}. ［<span style="{time_style}">{show_time}</span> <span style="{source_style}">{source}({source_seq})</span>］
            {title} 👉 <a href="{link}" target="_blank" style="{link_style}">🔗</a>
        </li>
        """
        news_html_list.append(news_html)

    # 有新资讯才发送邮件（小白不用动）
    if news_html_list:
        final_content = "\n".join(news_html_list)
        email_title = f"快讯 | {display_bj_date}"  # 邮件主题：完整北京时间（年-月-日）
        send_email(email_title, final_content, display_bj_date)  # 调用修改后的发送函数
    else:
        print("ℹ️  暂无新资讯，本次不推送邮件")

# 执行脚本（小白不用动）
if __name__ == "__main__":
    fetch_rss()

