"""
API Relay Monitor - FastAPI 应用入口
API 中转站监控系统
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.schemas import MessageResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("🚀 [启动] 初始化数据库...")
    await init_db()
    logger.info("✅ [启动] 数据库初始化完成")

    logger.info("🚀 [启动] 启动定时任务调度器...")
    start_scheduler()
    logger.info("✅ [启动] 调度器已启动")

    yield

    # 关闭时清理
    logger.info("⏹ [关闭] 停止调度器...")
    stop_scheduler()
    logger.info("✅ [关闭] 清理完成")


# 创建 FastAPI 应用
app = FastAPI(
    title="API Relay Monitor",
    description="API 中转站监控系统 - 爬取、分析、监控 LLM API 中转/代理站点",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由（必须在静态文件 mount 之前）
from app.routers import relay_sites, crawl_tasks, analysis, dashboard  # noqa: E402

app.include_router(relay_sites.router)
app.include_router(crawl_tasks.router)
app.include_router(analysis.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "api-relay-monitor", "version": "1.0.0"}


@app.get("/api/config", tags=["系统配置"])
async def get_config():
    """获取当前系统配置（脱敏）"""
    return {
        "llm_api_base": settings.LLM_API_BASE,
        "llm_model": settings.LLM_MODEL,
        "crawl_interval_minutes": settings.CRAWL_INTERVAL_MINUTES,
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
    }


@app.post("/api/config", tags=["系统配置"])
async def update_config():
    """更新系统配置（通过 .env 文件修改，此处仅返回提示）"""
    return MessageResponse(
        message="配置已通过 .env 文件管理，请修改 .env 后重启服务",
        success=True,
    )


# 挂载静态文件（前端 UI）
# 优先查找项目根目录的 frontend/，其次是 backend/static/
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_static_candidates = [
    os.path.join(_project_root, "frontend"),  # 开发模式: project/frontend/
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),  # Docker: backend/static/
]

STATIC_DIR = None
for candidate in _static_candidates:
    if os.path.exists(candidate) and os.path.exists(os.path.join(candidate, "index.html")):
        STATIC_DIR = candidate
        break

if STATIC_DIR:
    logger.info(f"📁 [静态文件] 目录: {STATIC_DIR}")

    @app.get("/")
    async def serve_index():
        """提供前端首页"""
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))

    # 静态资源文件（JS/CSS/images 等）
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static-files")

    logger.info("✅ [静态文件] 前端 UI 已挂载，访问 http://localhost:8000/ 查看")
else:
    logger.warning("⚠️  [静态文件] 未找到前端文件，仅 API 模式运行")
    logger.warning("   → 访问 http://localhost:8000/docs 查看 API 文档")

    @app.get("/")
    async def root():
        """系统根路径（无前端时显示 API 信息）"""
        return {
            "name": "API Relay Monitor",
            "description": "API 中转站监控系统",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }
