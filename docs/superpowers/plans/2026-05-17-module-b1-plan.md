# Module B.1 Implementation Plan: Backend Infrastructure + JWT Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for TDD cycle.

**Goal:** 搭建 JWT 用户认证基础设施（不修改现有 API，保持向后兼容）

**Architecture:**
- JWT-based authentication with bcrypt password hashing
- Dev mode fallback to demo user (id=1) when no token provided
- All new auth endpoints under `/api/v1/auth/`

---

## 新增文件清单

| 文件 | 职责 | 行数 |
|------|------|------|
| `app/core/security.py` | JWT工具函数 + password hashing | ~50 |
| `app/schemas/auth.py` | RegisterRequest, LoginRequest, TokenResponse | ~30 |
| `app/api/v1/endpoints/auth.py` | /register, /login 端点 | ~80 |
| `tests/test_auth.py` | TDD 测试用例（5个） | ~100 |
| `scripts/generate_jwt_secret.py` | JWT密钥生成工具 | ~20 |

**修改文件：**
| 文件 | 修改内容 |
|------|----------|
| `app/models/user.py` | 添加 `password_hash` 字段（nullable=True） |
| `app/db/seed.py` | demo 用户添加 `password_hash=None` |
| `app/main.py` | 注册 auth 路由 |

---

## 测试用例列表（TDD Red Phase）

```python
# tests/test_auth.py

def test_register_success():
    """注册新用户，期望 201 + access_token"""
    # POST /api/v1/auth/register with username/email/password
    # 期望: 201, {"user_id": N, "access_token": "..."}

def test_register_duplicate():
    """重复注册，期望 409"""
    # 同一 username 再次注册
    # 期望: 409, {"detail": "Username already exists"}

def test_login_success():
    """正确密码登录，期望 200 + token"""
    # POST /api/v1/auth/login with correct credentials
    # 期望: 200, {"access_token": "...", "token_type": "bearer"}

def test_login_wrong_password():
    """错误密码，期望 401"""
    # POST /api/v1/auth/login with wrong password
    # 期望: 401, {"detail": "Invalid credentials"}

def test_jwt_secret_generated():
    """JWT密钥生成工具"""
    # 运行 scripts/generate_jwt_secret.py
    # 期望: 输出有效密钥字符串
```

---

## 验证计划

### 1. pytest tests/test_auth.py
```
Expected: 5 tests, all PASS (after implementation)
```

### 2. 全量 pytest
```
Expected: 66+ passed, 0 failed
```

### 3. 冒烟测试路径A（12步）
```
Expected: All 12 steps PASS
```

### 4. 冒烟测试路径B（13步）
```
Expected: All 13 steps PASS
```

---

## 实现顺序

1. **Step 1:** 创建 `app/core/security.py` - JWT工具函数
2. **Step 2:** 创建 `app/schemas/auth.py` - Pydantic模型
3. **Step 3:** 扩展 `app/models/user.py` - 添加password_hash
4. **Step 4:** 创建 `app/api/v1/endpoints/auth.py` - 端点
5. **Step 5:** 更新 `app/db/seed.py` - demo用户兼容
6. **Step 6:** 注册路由到 `app/main.py`
7. **Step 7:** 创建 `scripts/generate_jwt_secret.py`
8. **Step 8:** 编写 TDD 测试 `tests/test_auth.py`（先写测试，验证RED）
9. **Step 9:** 实现并通过所有测试（GREEN）
10. **Step 10:** 运行全量验证

---

## 关键设计决策

### password_hash nullable=True
现有 demo 用户 (id=1) 没有 password_hash，新用户必须有。为兼容现有数据：
```python
password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
```

### Dev Mode Fallback
在 B.1 实现时，所有现有 API 仍使用 fallback 到 demo 用户：
```python
def get_current_user(authorization: str = Header(None)) -> int:
    if not authorization:
        return 1  # demo user fallback
    # JWT 验证逻辑在 B.2 实现
```

### JWT Secret
使用环境变量 `JWT_SECRET`，默认值 `dev-secret-change-in-production` 仅用于开发。

---

## 约束

- ❌ 不修改现有 API 的依赖注入
- ❌ 不修改前端代码
- ❌ 不替换硬编码 user_id=1
- ✅ 新增 auth 端点可用
- ✅ 现有 API 保持 fallback 到 demo 用户
- ✅ 必须保持 pytest 66+ 和冒烟测试双路径通过