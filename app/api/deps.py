from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

# HTTPException, status：抛出 HTTP 错误和状态码。
#
# HTTPBearer：一个安全方案，要求请求头中包含 Authorization: Bearer <token>。
#
# HTTPAuthorizationCredentials：用于获取 token 字符串的对象。


from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user



security = HTTPBearer()

# 创建一个 HTTP Bearer 安全依赖项。当在路由中使用 Depends(security) 时，
# FastAPI 会自动检查请求头中的 Authorization: Bearer xxx，并返回 HTTPAuthorizationCredentials 对象。如果没有提供或格式错误，会返回 401



async def require_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await get_current_user(db, credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return user

