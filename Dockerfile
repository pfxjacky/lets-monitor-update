# 使用 Python 3.9 的官方基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制 requirements.txt 到容器内
COPY requirements.txt /app/

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件到容器
COPY . /app/

# 设置环境变量
ENV FLASK_APP=web.py
ENV FLASK_ENV=production  

# 映射容器 5000 端口到主机
EXPOSE 5556

# 设置容器启动命令
CMD ["python", "web.py"]
