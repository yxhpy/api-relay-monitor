<div align="center">

# 🔍 API 中转站智能监控系统

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](https://github.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)](https://docker.com)

**智能监控 API 中转站的可用性、价格和服务状态，LLM 驱动的自动化分析**

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [配置说明](#-配置说明) • [手动部署](#-手动部署) • [API 文档](#-api-文档)

</div>

---

## 📖 项目简介

API 中转站智能监控系统是一个全自动化工具，用于实时监控各种 OpenAI 兼容 API 中转服务（如 API2D、OhMyGPT 等）的健康状态、价格变化和服务可用性。系统集成 LLM 大语言模型能力，能够智能分析监控数据并生成可读性强的分析报告，同时支持通过 Telegram Bot 进行消息推送。

## ✨ 功能特性

### 🔎 数据采集
- 🌐 **多源爬取** — 自动抓取主流 API 中转站的服务信息、价格数据
- ⏱️ **定时任务** — 支持自定义爬取间隔，默认每 8 小时执行一次
- 📊 **结构化存储** — 将采集的数据标准化入库，便于分析比对

### 🤖 智能分析
- 🧠 **LLM 驱动** — 利用大语言模型自动分析中转站的服务质量与性价比
- 📝 **自动报告** — 生成易读的监控分析报告，包含趋势变化和异常提醒
- 💡 **智能推荐** — 根据需求场景自动推荐最优的中转服务方案

### 📢 通知推送
- ✈️ **Telegram 推送** — 监控结果和异常告警实时推送到 Telegram
- 🔔 **多级告警** — 根据不同严重程度发送差异化通知
- 📋 **报告摘要** — 定期推送精简版监控报告

### 🛠️ 系统特性
- 🐳 **Docker 部署** — 一键部署，开箱即用
- 📱 **Web 界面** — 现代化的响应式前端监控面板
- 🔒 **安全可靠** — 环境变量管理敏感配置，数据本地存储
- ⚡ **高性能** — 异步架构，轻量级 SQLite 数据库

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Container                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                   FastAPI Backend                       │  │
│  │                                                        │  │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │  爬虫引擎  │  │  LLM 分析引擎  │  │  定时任务调度器  │  │  │
│  │  │  Crawler  │  │  AI Analyzer  │  │   Scheduler     │  │  │
│  │  └─────┬────┘  └──────┬───────┘  └────────┬────────┘  │  │
│  │        │               │                    │           │  │
│  │        ▼               ▼                    ▼           │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │              数据层 (SQLite + aioSQLite)          │  │  │
│  │  └──────────────────────────────────────────────────┘  │  │
│  │        │                                               │  │
│  │        ▼                                               │  │
│  │  ┌──────────────┐                                     │  │
│  │  │  REST API    │◄──── HTTP / WebSocket               │  │
│  │  └──────┬───────┘                                     │  │
│  └─────────┼─────────────────────────────────────────────┘  │
│            │                                                │
│  ┌─────────▼─────────────────────────────────────────────┐  │
│  │             前端静态文件 (HTML/CSS/JS)                  │  │
│  │                  监控面板 Dashboard                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌──────────────┐              ┌──────────────┐
  │  目标中转站    │              │ Telegram Bot  │
  │  API2D 等    │              │   消息推送     │
  └──────────────┘              └──────────────┘
```

## 🚀 快速开始

### 前提条件

- [Docker](https://docs.docker.com/get-docker/) 已安装
- [Docker Compose V2](https://docs.docker.com/compose/) 已安装
- 至少一个 OpenAI 兼容 API 的密钥

### 三步部署

```bash
# 1️⃣ 克隆项目
git clone https://github.com/your-username/api-relay-monitor.git
cd api-relay-monitor

# 2️⃣ 一键部署
chmod +x deploy.sh && ./deploy.sh

# 3️⃣ 访问系统
# 打开浏览器访问 http://localhost:8900
```

部署脚本会自动引导你完成 `.env` 配置文件的设置。

### 手动部署

如果不使用部署脚本，可以手动执行以下步骤：

```bash
# 1. 创建配置文件
cp .env.example .env

# 2. 编辑配置（填入你的 API Key 等信息）
nano .env

# 3. 创建数据目录
mkdir -p data

# 4. 构建并启动
docker compose up -d

# 5. 查看日志
docker compose logs -f
```

## ⚙️ 配置说明

所有配置项通过项目根目录的 `.env` 文件管理。复制 `.env.example` 作为起点：

```bash
cp .env.example .env
```

### 必填配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `LLM_API_KEY` | LLM API 密钥 | `sk-xxxxxxxx` |
| `LLM_API_BASE` | API 基础地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 使用的模型名称 | `gpt-4o-mini` |

### 可选配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 空（不推送） |
| `TELEGRAM_CHAT_ID` | Telegram 聊天 ID | 空（不推送） |
| `CRAWL_INTERVAL_MINUTES` | 爬取间隔（分钟） | `480`（8 小时） |
| `DATABASE_URL` | 数据库连接地址 | `sqlite+aiosqlite:///./data/relay_monitor.db` |

### LLM 配置说明

系统支持任何 **OpenAI 兼容 API**，包括但不限于：

- ✅ OpenAI 官方 API
- ✅ Azure OpenAI
- ✅ Anthropic（通过兼容层）
- ✅ 本地模型（如 Ollama、vLLM）
- ✅ 国内中转 API

只需修改 `LLM_API_BASE` 和 `LLM_API_KEY` 即可切换。

### Telegram 推送配置

1. 通过 [@BotFather](https://t.me/BotFather) 创建 Bot，获取 Token
2. 通过 [@userinfobot](https://t.me/userinfobot) 获取你的 Chat ID
3. 将 Token 和 Chat ID 填入 `.env` 文件

## 🔧 手动部署（非 Docker）

### 环境要求

- Python 3.11+
- pip 包管理器

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-username/api-relay-monitor.git
cd api-relay-monitor

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r backend/requirements.txt

# 4. 配置环境变量
cp .env.example .env
nano .env

# 5. 启动服务
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 `http://localhost:8000` 即可使用。

## 📡 API 文档

启动服务后，访问以下地址查看自动生成的 API 文档：

| 文档类型 | 地址 |
|----------|------|
| Swagger UI | `http://localhost:8900/docs` |
| ReDoc | `http://localhost:8900/redoc` |

### 主要 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/monitor/status` | 获取监控状态 |
| `GET` | `/api/monitor/data` | 获取监控数据 |
| `POST` | `/api/monitor/crawl` | 手动触发爬取 |
| `GET` | `/api/monitor/report` | 获取分析报告 |

> 详细 API 参数和返回值请参考 Swagger 文档。

## 🖼️ 系统截图

> 📸 截图待补充

| 监控面板 | 分析报告 |
|----------|----------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Report](docs/screenshots/report.png) |

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| **后端框架** | [FastAPI](https://fastapi.tiangolo.com/) — 高性能异步 Python Web 框架 |
| **ASGI 服务器** | [Uvicorn](https://www.uvicorn.org/) — 轻量级 ASGI 服务器 |
| **数据库** | [SQLite](https://sqlite.org/) + [aiosqlite](https://aiosqlite.omnilib.dev/) — 异步轻量数据库 |
| **ORM** | [SQLAlchemy](https://www.sqlalchemy.org/) — Python SQL 工具包 |
| **AI 引擎** | OpenAI Compatible API — LLM 智能分析 |
| **前端** | HTML5 / CSS3 / JavaScript — 原生现代化前端 |
| **容器化** | [Docker](https://docker.com/) + [Docker Compose](https://docs.docker.com/compose/) |
| **消息推送** | [Telegram Bot API](https://core.telegram.org/bots/api) |
| **HTTP 客户端** | [httpx](https://www.python-httpx.org/) — 异步 HTTP 请求 |

## 📋 常用运维命令

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看实时日志
docker compose logs -f

# 查看最近 100 行日志
docker compose logs --tail 100

# 重新构建并启动
docker compose up -d --build

# 查看容器状态
docker compose ps

# 进入容器调试
docker compose exec api-relay-monitor /bin/bash

# 清理数据重新开始
docker compose down -v
rm -rf data/
```

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐ Star 支持一下！**

Made with ❤️ by the community

</div>
