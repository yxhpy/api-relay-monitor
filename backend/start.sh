#!/bin/bash
# API Relay Monitor 启动脚本

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 创建数据目录
mkdir -p data

# 检查并创建 .env 文件（如果不存在）
if [ ! -f .env ]; then
    echo "# 创建默认配置文件 .env"
    cat > .env << 'EOF'
# LLM 配置
LLM_API_KEY=sk-your-api-key
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Telegram 通知（可选）
# TELEGRAM_BOT_TOKEN=your-bot-token
# TELEGRAM_CHAT_ID=your-chat-id

# 爬虫间隔（分钟）
CRAWL_INTERVAL_MINUTES=480

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./data/relay_monitor.db

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
EOF
    echo "已创建 .env 配置文件，请根据需要修改"
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt -q

# 启动应用
echo "启动 API Relay Monitor..."
exec python -m uvicorn app.main:app \
    --host "${APP_HOST:-0.0.0.0}" \
    --port "${APP_PORT:-8000}" \
    --reload
