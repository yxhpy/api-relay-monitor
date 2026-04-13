"""
API Relay Monitor - 数据库配置
使用 SQLAlchemy 异步引擎
"""

from urllib.parse import urlparse
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# 确保数据目录存在
_db_url = settings.DATABASE_URL
_parsed = urlparse(_db_url)
if _parsed.scheme.startswith("sqlite"):
    # urlparse 对 sqlite:///./data/db.db 返回 path="/./data/db.db"
    # 需要提取实际路径部分（去掉开头的 / 如果是相对路径）
    db_path = _parsed.path
    if db_path.startswith("/./"):
        # 相对路径: sqlite:///./data/db.db → ./data/db.db
        db_path = db_path[1:]
    elif db_path.startswith("/") and not db_path.startswith("//"):
        # 绝对路径: sqlite:////app/data/db.db → /app/data/db.db
        pass
    db_dir = Path(db_path).parent
    if db_dir and str(db_dir) != ".":
        db_dir.mkdir(parents=True, exist_ok=True)


# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
)

# 创建异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明性基类"""
    pass


async def get_db() -> AsyncSession:
    """依赖注入：获取数据库会话"""
    async with async_session() as session:
        try:
            yield session
            if session.in_transaction() and session.is_active:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库，创建所有表"""
    async with engine.begin() as conn:
        from app.models import Base  # noqa: F811
        await conn.run_sync(Base.metadata.create_all)
