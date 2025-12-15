# 导入工具（小白不用动）
import feedparser
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import html
import re

# ---------------------- 不用填！留空！脚本从安全区读信息 ----------------------
GMAIL_EMAIL = ""  # Gmail发件邮箱（留空）
GMAIL_APP_PASSWORD = ""  # 16位应用专用密码（留空）
RECEIVER_EMAILS = ""  # 收件人邮箱（留空）
# ------------------------------------------------------------------

# 数据源（路透社+彭博社，小白不用动）
RSS_SOURCES = [
    ("https://reutersnew.buzzing.cc/feed.xml", "路透社"),
    ("https://bloombergnew.buzzing.cc/feed.xml", "彭博社")
]

# 邮件颜色（橙色时间、红色路透社、蓝色彭博社、绿色🔗，小白不用动）
COLORS = {
    "time": "#F97316",       # 时间：橙色
    "reuters": "#E63946",    # 路透社：红色
    "bloomberg": "#1D4ED8",  # 彭博社：蓝色
    "link": "#16A34A",       # 链接：绿色
    "title": "#2E4057"       # 主标题：深蓝色
}

# 防重复：读已发资讯ID（小白不用动）
def get_pushed_ids():
    if not os.path.exists("pushed_ids.txt"):
        return set()
    with open("pushed_ids.txt", "r", encoding="utf-8") as f:
        return set(f.read().splitlines())

# 防重复：存已发资讯ID（小白不用动）
def save_pushed_id(id):
    with open("pushed_ids.txt", "a", encoding="utf-8") as f:
        f.write(f"{id}\n")

# 发送邮件（Gmail发件，小白不用动）
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
    msg["From"] = GMAIL_EMAIL
    msg["To"] = RECEIVER_EMAILS
    msg["Subject"] = subject

    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        smtp.sendmail(GMAIL_EMAIL, RECEIVER_EMAILS.split(","), msg.as_string())
        smtp.quit()
        print("✅ 邮件推送成功！发件人：Gmail")
    except smtplib.SMTPAuthenticationError:
        print("❌ Gmail登录失败！检查邮箱和应用密码是否正确")
    except Exception as e:
        print(f"❌ 推送失败：{e}")

# 提取资讯时间（分时不变，小白不用动）
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

# 转换完整北京时间（年-月-日，小白不用动）
def get_news_bj_info(entry):
    try:
        entry_time = entry.get("updated", entry.get("published", ""))
        if entry_time:
            utc_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
            bj_time = utc_time + timedelta(hours=8)
            return bj_time.timestamp(), bj_time.strftime("%Y-%m-%d")
        current_bj = datetime.now()
        return current_bj.timestamp(), current_bj.strftime("%Y-%m-%d")
    except:
        current_bj = datetime.now()
        return current_bj.timestamp(), current_bj.strftime("%Y-%m-%d")

# 核心逻辑（抓资讯+排序+双序号，小白不用动）
def fetch_rss():
    pushed_ids = get_pushed_ids()
    all_news = []
    source_counter = {"路透社": 0, "彭博社": 0}
    global_counter = 0

    for rss_url, source in RSS_SOURCES:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                entry_id = entry.get("id", "").strip()
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                content = entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""

                if entry_id not in pushed_ids and entry_id and title and link.startswith(("http", "https")):
                    show_time = get_show_time(entry, content)
                    bj_timestamp, news_bj_date = get_news_bj_info(entry)
                    all_news.append((bj_timestamp, source, show_time, title, link, entry_id, news_bj_date))
                    save_pushed_id(entry_id)
        except Exception as e:
            print(f"⚠️ {source}资讯抓取出错，不影响其他")

    all_news.sort(key=lambda x: -x[0])
    news_html_list = []

    display_bj_date = all_news[0][6] if all_news else datetime.now().strftime("%Y-%m-%d")

    for news in all_news:
        bj_timestamp, source, show_time, title, link, _, _ = news
        global_counter += 1
        source_counter[source] += 1
        source_seq = source_counter[source]

        time_style = f"color:{COLORS['time']};font-weight:bold;"
        source_color = COLORS["reuters"] if source == "路透社" else COLORS["bloomberg"]
        source_style = f"color:{source_color};font-weight:bold;"
        link_style = f"color:{COLORS['link']};"

        news_html = f"""
        <li>
            {global_counter}. ［<span style="{time_style}">{show_time}</span> <span style="{source_style}">{source}({source_seq})</span>］
            {title} 👉 <a href="{link}" target="_blank" style="{link_style}">🔗</a>
        </li>
        """
        news_html_list.append(news_html)

    if news_html_list:
        final_content = "\n".join(news_html_list)
        email_title = f"快讯 | {display_bj_date}"
        send_email(email_title, final_content, display_bj_date)
    else:
        print("ℹ️  暂无新资讯，不推送")

if __name__ == "__main__":
    fetch_rss()
