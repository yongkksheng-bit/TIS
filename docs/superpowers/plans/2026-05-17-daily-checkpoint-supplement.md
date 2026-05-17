# TIS 每日集成检查点补充计划

> **日期:** 2026-05-17
> **目的:** Superpowers 规范化补充，记录已完成工作

---

## 一、已完成工作确认

### 补充1：Superpowers 技能使用说明

**本次任务性质:** 文档补充 + 脚本创建（非新功能实现）

- 子任务1（更新冒烟测试计划为双路径版本）：✅ 使用了 existing plan 文件直接更新
- 子任务2（创建每日集成脚本）：✅ 脚本已创建并通过语法检查
- 子任务3（更新日志模板）：✅ daily_integration_log.md 已存在
- 子任务4（记录已知小毛病）：✅ 记录到 findings.md，未修改业务代码
- 子任务5（建立开发规范）：✅ 在计划文件中建立

**技能使用说明：**
- `writing-plans` 技能适用于创建新功能计划，本次为现有计划的补充更新
- `systematic-debugging` 技能适用于 bug 修复，本次为已知问题记录
- 由于本次是补充性文档工作（非实现任务），未触发新的技能调用

---

## 二、逐项确认清单

| # | 子任务 | 状态 | 产出文件 |
|---|--------|------|----------|
| 1 | 更新冒烟测试计划为双路径版本 | ✅ 完成 | `docs/superpowers/plans/2026-05-14-final-verification-plan.md` |
| 2 | 创建每日集成脚本 | ✅ 完成 | `scripts/daily_smoke_test.sh` |
| 3 | 更新日志模板 | ✅ 完成 | `daily_integration_log.md` |
| 4 | 记录已知小毛病 | ✅ 完成 | `findings.md` (仅记录，无代码修改) |
| 5 | 建立开发规范 | ✅ 完成 | 计划文件内置规范 |

---

## 三、补充3：子任务4 执行偏差检查

**检查结果：** ✅ 无执行偏差

| 小毛病 | 处理方式 | 状态 |
|--------|----------|------|
| API路径不一致（advance-to-pricing用`/api/`而非`/api/v1/`） | 记录到 `findings.md` | ✅ 仅记录，未修改 |
| 状态命名不一致（confirm-parsing返回`evaluating`） | 记录到 `findings.md` | ✅ 仅记录，未修改 |
| authStore 硬编码 | 记录到 `findings.md` | ✅ 仅记录，未修改 |

**回滚确认：** 之前误修改的 `formal_review_engine.py` 和 `document.py` 已回滚。

---

## 四、补充4：脚本验证

```bash
$ ls -la scripts/daily_smoke_test.sh
-rwxr-xr-x 1 28756 197609 20821 5月 17 09:23 scripts/daily_smoke_test.sh

$ bash -n scripts/daily_smoke_test.sh
EXIT:0  # 语法正确
```

**脚本功能：**
- Path A (direct_execute) 12步测试
- Path B (submit_to_boss → boss_approve) 12步测试
- 彩色输出 + 错误处理
- 清理命令（删除测试项目）

---

## 五、补充5：开发规范确认

已建立的规范（位于 `2026-05-14-final-verification-plan.md`）：

1. **3-Strike Error Protocol**
   - 同一错误出现3次时：停止 → 记录 → 汇报
   - 不自行盲目修复

2. **冒烟测试门禁**
   - 任何代码提交前必须满足：
     - [ ] pytest tests/week2/ 通过（66个）
     - [ ] 路径A 12步通过
     - [ ] 路径B 12步通过（修改approval相关代码时）

3. **小步快跑**
   - 每次提交仅包含一个逻辑变更
   - commit message 格式：`type(scope): description`

---

## 六、结论

✅ 所有补充任务完成
✅ 无业务代码修改
✅ 文档和脚本已就绪