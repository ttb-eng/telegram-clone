import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    phone: str = Field(..., pattern=r"^\+?[1-9]\d{6,14}$")
    username: str = Field(..., min_length=3, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    phone: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    phone: str
    username: str
    display_name: str
    avatar_url: str | None = None
    bio: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

#model_config = {"from_attributes": True}：这是 Pydantic v2 的配置，允许从 ORM 对象（SQLAlchemy 模型实例）自动转换，
# 相当于旧版的 orm_mode = True。可以用 UserResponse.model_validate(user_obj) 将数据库对象转为响应 JSON。


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
#登录接口返回这个格式：access_token 是 JWT 字符串，token_type 固定 bearer，user 嵌套用户信息。

class UserUpdate(BaseModel):
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None


#接口的“合同”，定义了数据应该长什么样，FastAPI 会自动根据这些模型做请求校验、响应格式化。