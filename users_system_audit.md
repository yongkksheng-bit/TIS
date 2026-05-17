# TIS 用户系统审计报告

> 日期: 2026-05-14
> 审计范围: 用户系统设计、硬编码 user_id、认证机制

---

## 执行摘要

**结论: TIS 是单用户 Demo 系统，用户系统未实现。**

- `get_current_user()` 永远返回 `None`
- 前端 `authStore` 硬编码 `currentUser.id = 1`
- 数据库 `users` 表为空（0行）
- 所有 `validated_by`、`estimated_by`、`reviewed_by` 字段的 `user_id=1` 是硬编码占位符

---

## 1. 用户系统现状

### 1.1 有无用户注册/登录 API？

| API | 状态 | 说明 |
|-----|------|------|
| `POST /api/auth/register` | ❌ 不存在 | 无注册端点 |
| `POST /api/auth/login` | ❌ 不存在 | 无登录端点 |
| `GET /api/auth/me` | ❌ 不存在 | 无用户信息端点 |

### 1.2 `get_current_user()` 实现

**文件:** `app/dependencies.py:46-59`

```python
def get_current_user() -> Optional[dict]:
    """
    Returns None if not authenticated.
    Actual implementation will decode JWT token from Authorization header.
    """
    # Placeholder - actual implementation will parse JWT
    return None
```

**结论:** `get_current_user()` 永远返回 `None`，认证系统未实现。

### 1.3 前端 authStore

**文件:** `frontend/src/stores/authStore.ts`

```typescript
const currentUser = ref<User>({
  id: 1,
  username: 'specialist',
  role: 'specialist'
})
```

**结论:** 前端硬编码用户 ID=1，无登录流程。

### 1.4 用户打开系统首页看到什么？

- **前端路由:** 无登录保护，直接进入 Dashboard
- **实际行为:** 前端使用硬编码的 `currentUser.id=1` 调用 API
- **无需登录:** 系统是内部工具，假设操作用户固定为 ID=1

---

## 2. 硬编码 user_id=1 的位置清单

### 2.1 按严重程度分类

| 文件 | 行号 | 上下文 | 类型 |
|------|------|--------|------|
| `projects.py` | 533 | `current_user_id = 1  # placeholder` | 显式占位符 |
| `projects.py` | 573 | `user_id = current_user.get("id") if current_user else 1` | 隐式默认值 |
| `pricing.py` | 88 | `estimated_by=1,  # TODO: from auth context` | 显式占位符 |
| `review.py` | 156 | `outcome.reviewed_by = 1  # TODO: from auth context` | 显式占位符 |
| `review.py` | 206 | `engine.revive_draft(user_id=1, reason="rebid")` | 硬编码 |
| `formal_review.py` | 405 | `user_id = data.get("user_id", 1)` | 隐式默认值 |

### 2.2 硬编码 vs 有意设计

| 类型 | 数量 | 说明 |
|------|------|------|
| 显式占位符 (`# TODO`) | 3 | 代码注释明确说明需要实现认证 |
| 隐式默认值 (`else 1`) | 2 | 当 `current_user` 为 None 时使用 1 |
| 硬编码 | 1 | `revive_draft(user_id=1)` 无 TODO 注释 |

### 2.3 设计决策判断

**结论: 全部是"临时占位符"，不是设计决策。**

证据：
- 代码中有 `# TODO: from auth context` 注释
- `get_current_user()` 返回 `None` 是明确的占位符实现
- 数据库 `users` 表为空，说明从未创建过用户数据

---

## 3. 系统启动流程缺失

### 3.1 种子数据清单

| 数据 | 状态 | 说明 |
|------|------|------|
| users | ❌ 缺失 | 无种子脚本创建默认用户 |
| projects | ✅ 可有可无 | 测试可临时创建 |
| knowledge_chunks | ✅ 已有 | 13,726 条历史数据 |
| historical_tenders | ✅ 已有 | 14 条 |
| historical_bids | ✅ 已有 | 14 条 |

### 3.2 docker-compose 初始化

**检查:** `docker-compose.yml` 中无 `command` 或 `entrypoint` 脚本调用种子数据初始化。

**结论:** 无自动初始化流程。

### 3.3 没有"第一个管理员"的创建方式

系统设计文档中提到"需要管理员创建用户"，但：
- 无管理员注册 API
- 无初始密码设置
- 无种子管理员账户

---

## 4. 前端视角分析

### 4.1 路由保护检查

**问题:** 前端 DashboardView.vue 是否有登录保护？

**结论:** 无登录保护。

```typescript
// AppLayout.vue 或 main.ts 中未发现 auth guard
```

### 4.2 前端如何"认为"已登录

```typescript
// authStore.ts 硬编码
const currentUser = ref<User>({
  id: 1,
  username: 'specialist',
  role: 'specialist'
})
```

前端直接假设用户 ID=1，无需任何登录流程。

---

## 5. 数据库外键问题分析

### 5.1 当前错误

```
IntegrityError: validated_by = 1 失败
原因: users 表为空（0行），无 ID=1 的用户
```

### 5.2 问题本质

`ocr_extractions.validated_by` 是 **NOT NULL** 外键，指向 `users.id`。

但系统设计中：
- 用户系统从未实现
- 数据库无用户数据
- 所有 user_id 引用都是硬编码占位符

### 5.3 字段设计矛盾

| 字段 | 约束 | 设计意图 |
|------|------|----------|
| `ocr_extractions.validated_by` | NOT NULL FK → users.id | 要求有效的用户验证 |
| 实际情况 | users 表为空 | 无法满足 FK 约束 |

---

## 6. 建议修复方案

### 6.1 方案A：实现完整的用户系统（正确但工作量大）

1. 实现 `POST /api/auth/register`
2. 实现 `POST /api/auth/login` (返回 JWT)
3. 修改 `get_current_user()` 解析 JWT
4. 添加数据库种子脚本创建第一个管理员
5. 前端添加登录页面和 token 存储

**工作量:** 约 2-3 天

### 6.2 方案B：改为允许 NULL + 系统用户（最小修复）

**如果 TIS 确实是单用户系统：**

1. 将 `ocr_extractions.validated_by` 改为 **NULLABLE**（系统可接受未验证状态）
2. 在数据库中创建 **系统用户** (id=1, username='system')
3. 将所有占位符 `user_id=1` 改为从 `get_current_user()` 获取，为 NULL 时用 system 用户

```sql
-- 添加系统用户
INSERT INTO users (id, username, role, created_at)
VALUES (1, 'system', 'system', NOW());

-- 将 validated_by 改为 nullable
ALTER TABLE ocr_extractions
ALTER COLUMN validated_by DROP NOT NULL;
```

### 6.3 方案C：接受 Demo 模式（最简方案）

**如果 TIS 只用于内部 Demo：**

在 `confirmation_service.py` 中，当 `user_id=1` 但 `users` 表为空时：
- 允许操作但不设置 `validated_by`
- 或者使用 `DEFAULT` 系统用户

```python
# 在 confirm_extraction 和 apply_correction 中
if user_id == 1 and not db.query(User).get(1):
    user_id = None  # 允许 system 操作
```

---

## 7. 修复优先级建议

| 优先级 | 任务 | 理由 |
|--------|------|------|
| P0 | 决定用户系统是否需要 | 影响所有后续决策 |
| P1 | 如果需要用户系统 → 方案A | 正确但工作量大 |
| P2 | 如果是 Demo → 方案B 或 C | 快速可用 |

---

## 8. 回答用户的4个问题

### Q1: 用户系统现状

- **注册 API:** 无
- **登录 API:** 无
- **前端登录页面:** 无（Dashboard 直接可访问）
- **当前用户:** 前端硬编码 `currentUser.id = 1`，无 token/session

### Q2: 硬编码 user_id=1 的扩散范围

| 位置 | 说明 |
|------|------|
| `projects.py:533,573` | 占位符，带 `# TODO` |
| `pricing.py:88` | 占位符，带 `# TODO` |
| `review.py:156,206` | 硬编码（无 TODO）|
| `formal_review.py:405` | 默认值 |

**性质:** 全部是占位符，不是设计决策

### Q3: 系统启动流程缺失

- **种子脚本:** 无（只有 `seed_standard_certs.py` 用于证书）
- **docker-compose 初始化:** 无用户创建
- **第一个用户:** 无创建方式

### Q4: 前端视角

- 用户看到 Dashboard（无需登录）
- 前端使用硬编码 ID=1
- 无登录流程
- 如果有登录页...不存在的设计问题

---

## 9. 根因总结

**这是"演示系统向生产系统过渡中的基础设施缺失"，不是简单的数据缺失。**

证据链：
1. `get_current_user()` → 返回 `None`（占位符）
2. `authStore` → 硬编码 `id=1`（绕过认证）
3. `users` 表 → 空（无种子数据）
4. `validated_by` → FK NOT NULL（要求有效用户）
5. **矛盾:** 要求的 vs 实现的

---

## 10. 结论

| 判断项 | 结论 |
|--------|------|
| 系统设计是否应有用户系统？ | **是** - 代码注释表明计划实现 |
| 实际实现了用户系统吗？ | **否** - 所有认证代码是占位符 |
| 硬编码 user_id=1 是错误吗？ | **是** - 在无用户系统中毫无意义 |
| 当前阻塞是"数据缺失"吗？ | **否** - 是"设计不完整" |

**系统处于 Demo 阶段，用户系统未实现。所有 user_id 引用都是临占位符，需要决定是实现完整认证还是采用 Demo 简化方案。**