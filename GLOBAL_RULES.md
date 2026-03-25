# TIS 项目全局开发规则

## 代码规范
1. Python类型注解：所有函数参数和返回值必须加类型注解
2. 错误处理：所有外部调用（DB/API）必须用try-except包装，抛出TISException
3. 日志：使用structlog，所有关键操作记录info日志，错误记录error日志

## 数据库规范
1. 所有表必须有created_at和updated_at字段
2. JSONB字段必须设置默认值{}，不允许null
3. 外键必须加索引（自动或手动）
4. 删除用软删除（is_deleted字段），不用物理删除

## 测试规范
1. 每个core/下的类必须有对应的test_文件
2. 测试数据放在tests/fixtures/，不得硬编码在测试文件中
3. 集成测试（依赖其他Week的）必须标记@pytest.mark.integration

## 文档规范
1. 复杂算法必须写注释说明业务逻辑（为什么这么做）
2. API endpoint必须有docstring说明输入输出格式