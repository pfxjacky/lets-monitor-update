import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from send import NotificationSender
import os
from pymongo import MongoClient
import cfscrape
import shutil
from dotenv import load_dotenv
from urllib.parse import urlparse
from msgparse import thread_message, comment_message
# Load variables from data/.env
load_dotenv('data/.env')


scraper = cfscrape.create_scraper()


class ForumMonitor:
    def __init__(self, config_path='data/config.json'):
        self.config_path = config_path
        self.mongo_host = os.getenv("MONGO_HOST", 'mongodb://localhost:27017/')
        self.load_config()

        self.mongo_client = MongoClient(self.mongo_host)
        self.db = self.mongo_client['forum_monitor']
        self.threads = self.db['threads']
        self.comments = self.db['comments']

        self.threads.create_index('link', unique=True)
        self.comments.create_index('comment_id', unique=True)

    # 简化版当前时间调用函数
    def current_time(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 简化配置加载
    def load_config(self):
        # 如果配置文件不存在，复制示例文件
        if not os.path.exists(self.config_path):
            shutil.copy('example.json', self.config_path)
        with open(self.config_path, 'r') as f:
            self.config = json.load(f)['config']
        self.notifier = NotificationSender(self.config_path)
        print("配置文件加载成功")

    def keywords_filter(self, text):
        keywords_rule = self.config.get('keywords_rule', '')
        if not keywords_rule.strip():
            return False
        or_groups = [group.strip() for group in keywords_rule.split(',')]
        for group in or_groups:
            # Split by + for AND keywords
            and_keywords = [kw.strip() for kw in group.split('+')]
            # Check if all AND keywords are in the text (case-insensitive)
            if all(kw.lower() in text.lower() for kw in and_keywords):
                return True
        return False


    # -------- AI 相关功能 --------
    def workers_ai_run(self, model, inputs):
        headers = {"Authorization": f"Bearer {self.config['cf_token']}"}
        input = { "messages": inputs }
        response = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{self.config['cf_account_id']}/ai/run/{model}", headers=headers, json=input)
        return response.json()

    def ai_filter(self, description, prompt):
        print('Using AI')
        inputs = [
            { "role": "system", "content": prompt},
            { "role": "user", "content": description}
        ]
        output = self.workers_ai_run(self.config['model'], inputs) # "@cf/qwen/qwen1.5-14b-chat-awq"
        print(output)
        # return output['result']['response'].split('END')[0]
        return output['result']['choices'][0]['message']['content'].split('END')[0]

    # -------- RSS LET/LES -----------
    def check_lets(self, urls):
        """
        遍历并解析所有配置中的 RSS 链接。原实现假定 URL 格式固定，
        如 https://lowendtalk.com/categories/offers/feed.rss，直接按照
        index 取出域名和分类容易在自定义 RSS 时抛出 IndexError。

        本实现使用 urllib.parse.urlparse 提取主域名，并尝试从 path
        中推断分类，如果无分类则默认为空字符串。任何网络错误
        或解析错误均打印日志但不会中断其他源的处理。
        """
        for url in urls:
            try:
                parsed = urlparse(url)
                # 提取主域名，如 lowendtalk、lowendspirit
                # 如果是多级子域，仅保留第一个标签，譬如 www.v2ex.com -> www
                host_parts = parsed.netloc.split('.')
                domain = host_parts[0] if host_parts else parsed.netloc
                # 从路径中提取分类，例如 categories/offers/feed.rss -> categories
                path_parts = [p for p in parsed.path.split('/') if p]
                category = path_parts[1] if len(path_parts) > 1 else (path_parts[0] if path_parts else '')
                print(f"[{self.current_time()}] 检查 {domain} {category or 'unknown'} RSS...")
                res = scraper.get(url)
                if res.status_code != 200:
                    print(f"获取 {domain} RSS 失败，状态码 {res.status_code}")
                    continue
                # 根据 xml 解析，兼容 atom 等命名空间
                soup = BeautifulSoup(res.text, 'xml')
                items = soup.find_all('item')
                # 对于 Atom，entry 标签等同于 item
                if not items:
                    items = soup.find_all('entry')
                for item in items[:6]:
                    self.convert_rss(item, domain, category)
            except Exception as e:
                print(f"处理 RSS {url} 时发生错误: {e}")
                continue

    # -------- EXTRA URLS -----------
    def check_extra_urls(self, urls):
        for url in urls:
            print(f"[{self.current_time()}] 检查 extra URL: {url}")
            # 检查数据库是否已存在
            thread = self.threads.find_one({'link': url})
            if thread:
                # 如果已有记录，尝试更新评论信息
                self.fetch_comments(thread)
            # 不存在则抓取并插入
            self.fetch_thread_page(url)

    # 将 RSS item 转成 thread_data
    def convert_rss(self, item, domain, category):
        """
        将 RSS/Atom item 转成 thread_data。不同源的字段名称和格式差异较大，
        因此采用多个候选标签，并提供健壮的异常处理。
        """
        # 标题
        title_el = item.find('title') or item.find('subject')
        title = title_el.text.strip() if title_el and title_el.text else ""

        # 链接
        link_el = item.find('link')
        link = ""
        if link_el:
            # link 可能有 text 或 href 属性
            if link_el.has_attr('href'):
                link = link_el['href']
            elif link_el.text:
                link = link_el.text.strip()
        # 如果 link 为空，从 guid 中尝试获取
        if not link:
            guid_el = item.find('guid')
            link = guid_el.text.strip() if guid_el and guid_el.text else ""

        # 描述/内容
        desc_text = ""
        # 优先解析 description
        desc_el = item.find('description') or item.find('summary') or item.find('content')
        if desc_el and desc_el.text:
            # 有些源内容嵌套 HTML，需要先用 BeautifulSoup 转换
            desc_text = BeautifulSoup(desc_el.text, 'lxml').get_text().strip()

        # 作者/创建者
        creator = ""
        creator_el = item.find('dc:creator') or item.find('author') or item.find('creator')
        if creator_el:
            # Atom author 可能是 <author><name>xxx</name></author>
            if creator_el.find('name'):
                creator = creator_el.find('name').text.strip()
            elif creator_el.text:
                creator = creator_el.text.strip()
        if not creator:
            creator = "Unknown"

        # 发布时间
        pub_date = datetime.now(timezone.utc)
        pub_date_text = None
        # 常见时间标签
        for tag in ['pubDate', 'published', 'updated']:
            el = item.find(tag)
            if el and el.text:
                pub_date_text = el.text.strip()
                break
        if pub_date_text:
            # 尝试解析不同格式的日期
            try:
                # 使用 email.utils 处理常见 RFC822/2822 时间格式
                import email.utils as eut
                dt = eut.parsedate_to_datetime(pub_date_text)
                # 如果没有时区，则假定为 UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                pub_date = dt
            except Exception:
                try:
                    # 尝试 ISO 8601 格式
                    pub_date = datetime.fromisoformat(pub_date_text.replace('Z', '+00:00'))
                except Exception:
                    # 未能解析则保持当前时间
                    pub_date = datetime.now(timezone.utc)

        thread_data = {
            'domain': domain,
            'category': category,
            'title': title,
            'link': link,
            'description': desc_text,
            'creator': creator,
            'pub_date': pub_date,
            'created_at': datetime.now(timezone.utc),
            'last_page': 1
        }

        self.handle_thread(thread_data)
        # 只有 lowendtalk/lowendspirit 等论坛帖子需要抓取评论，
        # 其他站点没有分页评论功能，可以跳过
        if domain in ['lowendtalk', 'lowendspirit']:
            self.fetch_comments(thread_data)

    # -------- 线程存储 + 通知 --------
    def handle_thread(self, thread):
        exists = self.threads.find_one({'link': thread['link']})
        if exists:
            return

        self.threads.insert_one(thread)
        # 发布时间 24h 内才推送
        if (datetime.now(timezone.utc) - thread['pub_date'].replace(tzinfo=timezone.utc)).total_seconds() <= 86400:
            if self.config.get('use_ai_filter', False):
                ai_description = self.ai_filter(thread['description'],self.config['thread_prompt'])
                if ai_description == "FALSE":
                    return
            else:
                ai_description = ""
            msg = thread_message(thread, ai_description)
            self.notifier.send_message(msg)

    # 新增：直接抓取单个线程页面并解析成 thread_data 格式
    def fetch_thread_page(self, url):
        res = scraper.get(url)
        if res.status_code != 200:
            print(f"获取页面失败 {url} 状态码 {res.status_code}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        item_header = soup.select_one("div.Item-Header.DiscussionHeader")
        page_title = soup.select_one("#Item_0.PageTitle")

        if not item_header or not page_title:
            print("结构不匹配")
            return None

        title = page_title.select_one("h1")
        title = title.text.strip() if title else ""

        creator = item_header.select_one(".Author .Username")
        creator = creator.text.strip() if creator else ""

        time_el = item_header.select_one("time")
        if time_el and time_el.has_attr("datetime"):
            pub_date_str = time_el["datetime"]
            try:
                pub_date = datetime.strptime(pub_date_str, "%Y-%m-%dT%H:%M:%S+00:00")
            except ValueError:
                pub_date = datetime.now(timezone.utc)  # 如果解析失败，使用当前时间
        else:
            pub_date = datetime.now(timezone.utc)

        category = item_header.select_one(".Category a")
        category = category.text.strip() if category else ""

        desc_el = soup.select_one(".Message.userContent")
        description = desc_el.get_text("\n", strip=True) if desc_el else ""

        parsed = urlparse(url)
        domain = parsed.netloc

        thread_data = {
            "domain": domain,
            "category": category,
            "title": title,
            "link": url,
            "description": description,
            "creator": creator,
            "pub_date": pub_date,
            "created_at": datetime.now(timezone.utc),
            "last_page": 1
        }

        self.handle_thread(thread_data)
        self.fetch_comments(thread_data)


    # -------- 评论抓取统一逻辑（LET / LES 一样） --------
    def fetch_comments(self, thread):
        last_page = self.threads.find_one({'link': thread['link']}).get('last_page', 1)

        while True:
            page_url = f"{thread['link']}/p{last_page}"
            res = scraper.get(page_url)

            if res.status_code != 200:
                # 更新 last_page
                self.threads.update_one(
                    {'link': thread['link']},
                    {'$set': {'last_page': last_page - 1}}
                )
                break

            self.parse_comments(res.text, thread)
            last_page += 1
            time.sleep(1)

    # -------- 通用评论解析 --------
    def parse_comments(self, html, thread):
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.find_all('li', class_='ItemComment')

        for it in items:
            cid = it.get('id')
            if not cid:
                continue
            cid = cid.split('_')[1]

            author = it.find('a', class_='Username').text
            role = it.find('span', class_='RoleTitle').text if it.find('span', class_='RoleTitle') else None
            msg = it.find('div', class_='Message').text.strip()
            created = it.find('time')['datetime']

            if self.config.get('comment_filter') == 'by_role':
                # by_role 过滤器，为 None '' 或者只有 member 则跳过
                if not role or role.strip().lower() == 'member':
                    continue
            if self.config.get('comment_filter') == 'by_author':
                # 只监控作者自己的后续更新
                if author != thread['creator']:
                    continue

            comment = {
                'comment_id': f"{thread['domain']}_{cid}",
                'thread_url': thread['link'],
                'author': author,
                'message': msg[:200].strip(),
                'created_at': datetime.strptime(created, "%Y-%m-%dT%H:%M:%S+00:00"),
                'created_at_recorded': datetime.now(timezone.utc),
                'url': f"{thread['link']}/comment/{cid}/#Comment_{cid}"
            }

            self.handle_comment(comment, thread)

    # -------- 存储评论 + 通知 --------
    def handle_comment(self, comment, thread):
        if self.comments.find_one({'comment_id': comment['comment_id']}):
            return

        self.comments.update_one({'comment_id': comment['comment_id']},
                                 {'$set': comment}, upsert=True)

        # 只推送 24 小时内的
        if (datetime.now(timezone.utc) - comment['created_at'].replace(tzinfo=timezone.utc)).total_seconds() <= 86400:
            if self.config.get('use_keywords_filter', False) and (not self.keywords_filter(comment['message'])):
                    return
            if self.config.get('use_ai_filter', False):
                ai_description = self.ai_filter(comment['message'],self.config['comment_prompt'])
                if ai_description == "FALSE":
                    return
            else:
                ai_description = ""
            msg = comment_message(thread, comment, ai_description)
            self.notifier.send_message(msg)

    # -------- 主循环 --------
    def start_monitoring(self):
        print("开始监控...")
        freq = self.config.get('frequency', 600)

        while True:
            self.check_extra_urls(urls=self.config.get('extra_urls', []))
            if not self.config.get('only_extra', False):
                # 处理 RSS 和 extra URLs
                self.check_lets(urls=self.config.get('urls', [
                    "https://lowendspirit.com/categories/offers/feed.rss",
                    "https://lowendtalk.com/categories/offers/feed.rss"
                ]))
            print(f"[{self.current_time()}] 遍历结束，休眠 {freq} 秒...")
            time.sleep(freq)

    # 外部重载配置方法
    def reload(self):
        print("重新加载配置...")
        self.load_config()
        
if __name__ == "__main__":
    monitor = ForumMonitor()
    monitor.start_monitoring()
