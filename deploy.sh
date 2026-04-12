#!/bin/bash

# API 中转站智能监控系统 - 一键部署脚本
# 使用方法: chmod +x deploy.sh && ./deploy.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  API 中转站智能监控系统 - 部署脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: 未检测到 Docker，请先安装 Docker${NC}"
    echo -e "${YELLOW}安装指南: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi

# 检查 Docker Compose 是否可用
if ! docker compose version &> /dev/null; then
    echo -e "${RED}错误: 未检测到 Docker Compose V2，请升级 Docker${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker 环境检测通过${NC}"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ 未找到 .env 配置文件，从模板创建...${NC}"
    cp .env.example .env
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}  请编辑 .env 文件，填入必要的配置信息！${NC}"
    echo -e "${RED}  特别是 LLM_API_KEY 等必填项。${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "编辑完成后重新运行此脚本。"
    echo -e "命令: ${YELLOW}nano .env${NC} 或 ${YELLOW}vim .env${NC}"
    
    # 询问是否立即编辑
    read -p "是否现在编辑配置文件？(y/n): " edit_choice
    if [[ "$edit_choice" =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    else
        echo -e "${YELLOW}请手动编辑 .env 后重新运行部署脚本。${NC}"
        exit 0
    fi
else
    echo -e "${GREEN}✓ 配置文件 .env 已存在${NC}"
fi

# 创建数据目录
mkdir -p data
echo -e "${GREEN}✓ 数据目录已就绪${NC}"

# 构建并启动
echo ""
echo -e "${BLUE}正在构建 Docker 镜像...${NC}"
docker compose build

echo ""
echo -e "${BLUE}正在启动服务...${NC}"
docker compose up -d

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "访问地址: ${YELLOW}http://localhost:8900${NC}"
echo ""
echo -e "常用命令:"
echo -e "  查看日志:   ${BLUE}docker compose logs -f${NC}"
echo -e "  停止服务:   ${BLUE}docker compose down${NC}"
echo -e "  重启服务:   ${BLUE}docker compose restart${NC}"
echo -e "  查看状态:   ${BLUE}docker compose ps${NC}"
echo ""

# 显示实时日志
read -p "是否查看实时日志？(y/n): " log_choice
if [[ "$log_choice" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}显示实时日志 (Ctrl+C 退出)...${NC}"
    echo ""
    docker compose logs -f
fi
