# LET MONITOR

DEMO：https://t.me/letleblessub

详细教程：https://vpslog.org/projects/let-monitor/

一个基于 Workers AI 的 LowEndTalk/LowEndSpirt 新帖/评论监控。获取到信息后，交由 AI 进行翻译、总结、筛选，并推送到 Telegram 等不同渠道。

## 功能

- **新帖监控**：监控 offer 区新帖，并由AI进行总结翻译。
- **评论监控**：监控帖子作者的后续评论，由AI筛选有价值评论推送。

## 限制

AI 需要调校，可能会输出预期以外的结果。

## 安装和配置

### Python 源码直连部署（手动部署）
如果你需要在本地运行或不支持 Docker 的环境中部署，请遵循以下步骤。

1. 环境准备
你需要自行安装并启动以下服务：

Python 3.8+

MongoDB：必须确保 MongoDB 服务已启动并运行在默认端口 27017（或需手动修改配置）。

2. 获取源代码
Bash

git clone https://github.com/pfxjacky/lets-monitor-update.git
cd lets-monitor-update
3. 安装依赖
建议使用虚拟环境：

Bash

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装项目依赖
pip install -r requirements.txt
4. 初始化配置
项目需要一个 data 目录用于存放数据，以及配置文件。

创建数据目录：

Bash

mkdir data
配置 Config 文件： 复制示例配置文件。根据原版文档说明，通常需要将 example.json 复制为 config.json。

Bash

cp example.json config.json
注意：如果程序报错找不到配置，尝试将 config.json 移动到 data/ 目录下（cp example.json data/config.json），因为新版可能调整了路径结构。

检查数据库连接： 打开 core.py 或 web.py（或查看 config.json），确认 MongoDB 的连接地址。如果是本地运行，通常不需要修改，默认为 localhost 或 127.0.0.1。如果代码中写死为 mongodb://mongo:27017（这是 Docker 内部主机名），你需要将其改为 mongodb://localhost:27017。

5. 启动程序
你可以选择启动 Web 界面模式或仅后台核心模式：

启动 Web 管理界面（推荐）：

Bash

python web.py
运行后访问 http://localhost:5556。

仅运行核心监控（无 GUI）：

Bash

python core.py
部署后配置指南（Web 面板设置）
无论使用哪种部署方式，启动后都需要在 Web 面板（http://IP:5556）完成以下核心配置才能正常工作。

1. 基础设置
RSS URLs：填入需要监控的 RSS 地址。

https://lowendtalk.com/categories/offers/feed.rss

https://lowendspirit.com/categories/offers/feed.rss

监控间隔：建议设置 300 - 600 秒（5-10分钟），避免被论坛封禁 IP。

2. 过滤器与 AI 配置（核心功能）
AI 过滤：要使用翻译和智能总结，你需要 Cloudflare Workers AI 的账号。

Account ID 和 API Token：在 Cloudflare 后台获取。

Model：选择一个合适的模型（如 @cf/meta/llama-3-8b-instruct）。

Prompt（提示词）：可以在面板中自定义提示词，让 AI 按照你的格式输出（如“提取价格、配置、优惠码”）。

3. 通知渠道配置
Telegram：

Bot Token：通过 @BotFather 获取。

Chat ID：将 Bot 拉入群组/频道后获取 ID。

微信/Webhook：根据需要配置。

4. 关键词过滤（可选）
支持 OR（逗号分隔）和 AND（加号连接）逻辑。

示例：vps+cn2, dedipath, 9929（表示监控包含 "vps"且包含"cn2"的帖子，或者包含 "dedipath" 的帖子，或者包含 "9929" 的帖子）。

常见问题
MongoDB 连接失败：请检查 MongoDB 是否已启动，且防火墙允许连接。Docker 模式下请确保 docker-compose.yml 中的 volume 权限正确。

无法推送通知：检查服务器是否能访问 Telegram API（国内服务器通常需要代理）。

AI 不工作：检查 Cloudflare API Token 是否有 Workers AI 的读写权限。

访问`5556`即可。需要提供 telegram 相关信息、Cloudflare Workers AI 凭据。如下图获取：

![alt text](image.png)

可以调整 prompt 和 model 适应不同需求

