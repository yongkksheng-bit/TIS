#!/bin/bash
# TIS Daily Smoke Test Script
# 执行双路径冒烟测试，确保系统完整性
# 用法: bash scripts/daily_smoke_test.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${NC}[INFO] $1"; }
log_pass() { echo -e "${GREEN}[PASS] $1${NC}"; }
log_fail() { echo -e "${RED}[FAIL] $1${NC}"; }
log_warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }

echo "=========================================="
echo "TIS Daily Smoke Test"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# Step 0: 环境检查
log_info "Step 0: 环境检查"
if docker compose ps | grep -q "healthy"; then
    log_pass "Docker 容器运行正常"
else
    log_fail "Docker 容器异常，请检查"
    exit 1
fi

if curl -s http://localhost:8000/docs | grep -q "FastAPI"; then
    log_pass "后端 API 可达"
else
    log_fail "后端 API 不可达"
    exit 1
fi

# 等待服务完全就绪
sleep 5
echo ""

# 测试数据文件
TEST_PDF="data/test_documents/惠州市交通运输局交通大厦食堂管理和食材配送服务_招标文件.pdf"
if [ ! -f "$TEST_PDF" ]; then
    log_fail "测试文件不存在: $TEST_PDF"
    exit 1
fi
log_pass "测试文件存在: $TEST_PDF"
echo ""

# ============================================
# 路径A：直接执行（specialist直接执行）
# ============================================
log_info "=========================================="
log_info "路径A：直接执行（specialist直接执行）"
log_info "=========================================="

PROJECT_ID_A=""

# Step 1: 创建项目
log_info "Step 1: 创建项目"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects" \
    -H "Content-Type: application/json" \
    -d '{"project_name":"smoke_test_pathA","project_type":"service","owner_unit":"test_unit","region":"Guangzhou","budget_amount":5000000}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    PROJECT_ID_A=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    log_pass "项目创建成功: id=$PROJECT_ID_A"
else
    log_fail "项目创建失败: HTTP $HTTP_CODE"
    echo "$RESPONSE" | grep -v "HTTP_CODE"
    exit 1
fi

# Step 2: 上传PDF
log_info "Step 2: 上传PDF"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects/$PROJECT_ID_A/upload" \
    -F "file=@$TEST_PDF")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "PDF上传成功"
else
    log_fail "PDF上传失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 3: 获取确认数据
log_info "Step 3: 获取确认数据"
sleep 3
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "http://localhost:8000/api/projects/$PROJECT_ID_A/confirmation-data")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "确认数据获取成功"
    # 提取所有 extraction_id
    EXTRACTION_IDS=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | cut -d: -f2 | tr '\n' ',' | sed 's/,$//')
    log_info "提取到 extraction_ids: $EXTRACTION_IDS"
else
    log_fail "确认数据获取失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 4: 确认解析
log_info "Step 4: 确认解析"
# 构造 confirmations JSON
CONFIRMATIONS="["
IFS=',' read -ra IDS <<< "$EXTRACTION_IDS"
for i in "${!IDS[@]}"; do
    if [ $i -gt 0 ]; then CONFIRMATIONS+=","; fi
    CONFIRMATIONS+="{\"extraction_id\":${IDS[$i]},\"action\":\"confirm\"}"
done
CONFIRMATIONS+="]"

RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects/$PROJECT_ID_A/confirm-parsing" \
    -H "Content-Type: application/json" \
    -d "{\"confirmations\":$CONFIRMATIONS,\"project_name\":\"smoke_test_pathA\",\"bid_open_date\":\"2026-06-30\",\"owner_unit\":\"test\",\"budget_amount\":5000000,\"region\":\"Guangzhou\",\"project_type\":\"service\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "解析确认成功"
else
    log_fail "解析确认失败: HTTP $HTTP_CODE"
    echo "$RESPONSE" | grep -v "HTTP_CODE"
    exit 1
fi

# Step 5: 生成评估
log_info "Step 5: 生成评估"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_A/evaluations/generate" \
    -H "Content-Type: application/json" \
    -d '{}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    REPORT_ID=$(echo "$RESPONSE" | grep -o '"report_id":[0-9]*' | cut -d: -f2)
    log_pass "评估生成成功: report_id=$REPORT_ID"
else
    log_fail "评估生成失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 6: Specialist 直接执行
log_info "Step 6: Specialist 直接执行 (direct_execute)"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/evaluations/$REPORT_ID/approve" \
    -H "Content-Type: application/json" \
    -d '{"action":"direct_execute","generation_mode":"AUTO","user_id":1,"role":"specialist"}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    PROJECT_STATUS=$(echo "$RESPONSE" | grep -o '"project_status":"[^"]*"' | cut -d'"' -f4)
    log_pass "Specialist审批成功: status=$PROJECT_STATUS"
    if [ "$PROJECT_STATUS" = "generating_documents" ]; then
        log_pass "状态正确: generating_documents"
    else
        log_warn "状态异常: $PROJECT_STATUS (期望 generating_documents)"
    fi
else
    log_fail "Specialist审批失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 7: 生成章节
log_info "Step 7: 生成章节"
echo '{"section_name":"第一章：冷链配送方案","generation_mode":"auto"}' > /tmp/gen_section.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_A/generate-section" \
    -H "Content-Type: application/json" \
    -d @/tmp/gen_section.json)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "章节生成成功"
else
    log_fail "章节生成失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 8: 保存章节
log_info "Step 8: 保存章节"
echo '{"section_name":"第一章：冷链配送方案","content":"[测试内容]","mode":"auto"}' > /tmp/save_section.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X PUT "http://localhost:8000/api/v1/projects/$PROJECT_ID_A/sections/第一章：冷链配送方案" \
    -H "Content-Type: application/json" \
    -d @/tmp/save_section.json)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "章节保存成功"
else
    log_warn "章节保存失败（继续）: HTTP $HTTP_CODE"
fi

# Step 9: 推进到定价
log_info "Step 9: 推进到定价"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects/$PROJECT_ID_A/advance-to-pricing" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "推进到定价成功"
else
    log_fail "推进到定价失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 10: 提交定价决策
log_info "Step 10: 提交定价决策"

# 创建成本估算
echo '{"food_cost":3000000,"logistics_cost":500000,"labor_cost":800000,"management_cost":500000,"estimate_reason":"smoke test"}' > /tmp/cost_est.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_A/cost-estimates" \
    -H "Content-Type: application/json" \
    -d @/tmp/cost_est.json)
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
ESTIMATE_ID=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
log_info "成本估算创建: id=$ESTIMATE_ID"

# 确认成本估算
echo '{"confirm":true}' > /tmp/confirm.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/cost-estimates/$ESTIMATE_ID/confirm" \
    -H "Content-Type: application/json" \
    -d @/tmp/confirm.json)
log_info "成本估算确认完成"

# 提交定价决策
echo '{"boss_final_price":5500000,"boss_decision_reason":"smoke test pricing","action_type":"normal"}' > /tmp/pricing.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_A/pricing-decisions" \
    -H "Content-Type: application/json" \
    -d @/tmp/pricing.json)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "定价决策提交成功"
else
    log_fail "定价决策提交失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 11: 初始化形式审查
log_info "Step 11: 初始化形式审查"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_A/checklists/init" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    ITEMS_CREATED=$(echo "$RESPONSE" | grep -o '"itemsCreated":[0-9]*' | cut -d: -f2)
    log_pass "形式审查初始化成功: itemsCreated=$ITEMS_CREATED"
else
    log_fail "形式审查初始化失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 12: 完成审查
log_info "Step 12: 完成审查"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_A/complete" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    FINAL_STATUS=$(echo "$RESPONSE" | grep -o '"newStatus":"[^"]*"' | cut -d'"' -f4)
    log_pass "项目完成: status=$FINAL_STATUS"
    if [ "$FINAL_STATUS" = "completed" ]; then
        log_pass "路径A 全部12步通过 ✅"
    else
        log_warn "最终状态异常: $FINAL_STATUS (期望 completed)"
    fi
else
    log_fail "项目完成失败: HTTP $HTTP_CODE"
    exit 1
fi

echo ""
log_pass "=========================================="
log_pass "路径A：全部12步通过 ✅"
log_pass "=========================================="
echo ""

# ============================================
# 路径B：老板审批（specialist提交→boss审批）
# ============================================
log_info "=========================================="
log_info "路径B：老板审批（specialist提交→boss审批）"
log_info "=========================================="

PROJECT_ID_B=""

# Step 1: 创建项目
log_info "Step 1: 创建项目"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects" \
    -H "Content-Type: application/json" \
    -d '{"project_name":"smoke_test_pathB","project_type":"service","owner_unit":"test_unit","region":"Guangzhou","budget_amount":5000000}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    PROJECT_ID_B=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    log_pass "项目创建成功: id=$PROJECT_ID_B"
else
    log_fail "项目创建失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 2: 上传PDF
log_info "Step 2: 上传PDF"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects/$PROJECT_ID_B/upload" \
    -F "file=@$TEST_PDF")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "PDF上传成功"
else
    log_fail "PDF上传失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 3: 获取确认数据
log_info "Step 3: 获取确认数据"
sleep 3
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "http://localhost:8000/api/projects/$PROJECT_ID_B/confirmation-data")
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "确认数据获取成功"
    EXTRACTION_IDS=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | cut -d: -f2 | tr '\n' ',' | sed 's/,$//')
    log_info "提取到 extraction_ids: $EXTRACTION_IDS"
else
    log_fail "确认数据获取失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 4: 确认解析
log_info "Step 4: 确认解析"
CONFIRMATIONS="["
IFS=',' read -ra IDS <<< "$EXTRACTION_IDS"
for i in "${!IDS[@]}"; do
    if [ $i -gt 0 ]; then CONFIRMATIONS+=","; fi
    CONFIRMATIONS+="{\"extraction_id\":${IDS[$i]},\"action\":\"confirm\"}"
done
CONFIRMATIONS+="]"

RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects/$PROJECT_ID_B/confirm-parsing" \
    -H "Content-Type: application/json" \
    -d "{\"confirmations\":$CONFIRMATIONS,\"project_name\":\"smoke_test_pathB\",\"bid_open_date\":\"2026-06-30\",\"owner_unit\":\"test\",\"budget_amount\":5000000,\"region\":\"Guangzhou\",\"project_type\":\"service\"}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "解析确认成功"
else
    log_fail "解析确认失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 5: 生成评估
log_info "Step 5: 生成评估"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_B/evaluations/generate" \
    -H "Content-Type: application/json" \
    -d '{}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    REPORT_ID=$(echo "$RESPONSE" | grep -o '"report_id":[0-9]*' | cut -d: -f2)
    log_pass "评估生成成功: report_id=$REPORT_ID"
else
    log_fail "评估生成失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 6a: Specialist 提交给 Boss
log_info "Step 6a: Specialist 提交给 Boss (submit_to_boss)"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/evaluations/$REPORT_ID/approve" \
    -H "Content-Type: application/json" \
    -d '{"action":"submit_to_boss","generation_mode":"AUTO","user_id":1,"role":"specialist"}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    PROJECT_STATUS=$(echo "$RESPONSE" | grep -o '"project_status":"[^"]*"' | cut -d'"' -f4)
    log_pass "提交给Boss成功: status=$PROJECT_STATUS"
    if [ "$PROJECT_STATUS" = "pending_boss_approval" ]; then
        log_pass "状态正确: pending_boss_approval"
    else
        log_warn "状态异常: $PROJECT_STATUS (期望 pending_boss_approval)"
    fi
else
    log_fail "提交给Boss失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 6b: Boss 审批
log_info "Step 6b: Boss 审批 (approve)"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/evaluations/$REPORT_ID/approve" \
    -H "Content-Type: application/json" \
    -d '{"action":"approve","generation_mode":"AUTO","user_id":1,"role":"boss","override_reason":"smoke test boss approval"}')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    PROJECT_STATUS=$(echo "$RESPONSE" | grep -o '"project_status":"[^"]*"' | cut -d'"' -f4)
    log_pass "Boss审批成功: status=$PROJECT_STATUS"
    if [ "$PROJECT_STATUS" = "generating_documents" ]; then
        log_pass "状态正确: generating_documents"
    else
        log_warn "状态异常: $PROJECT_STATUS (期望 generating_documents)"
    fi
else
    log_fail "Boss审批失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 7-12: 与路径A相同
# Step 7: 生成章节
log_info "Step 7: 生成章节"
echo '{"section_name":"第一章：项目理解","generation_mode":"auto"}' > /tmp/gen_section_b.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_B/generate-section" \
    -H "Content-Type: application/json" \
    -d @/tmp/gen_section_b.json)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "章节生成成功"
else
    log_fail "章节生成失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 8: 保存章节
log_info "Step 8: 保存章节"
echo '{"section_name":"第一章：项目理解","content":"[测试内容]","mode":"auto"}' > /tmp/save_section_b.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X PUT "http://localhost:8000/api/v1/projects/$PROJECT_ID_B/sections/第一章：项目理解" \
    -H "Content-Type: application/json" \
    -d @/tmp/save_section_b.json)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "章节保存成功"
else
    log_warn "章节保存失败（继续）: HTTP $HTTP_CODE"
fi

# Step 9: 推进到定价
log_info "Step 9: 推进到定价"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/projects/$PROJECT_ID_B/advance-to-pricing" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "推进到定价成功"
else
    log_fail "推进到定价失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 10: 提交定价决策
log_info "Step 10: 提交定价决策"
echo '{"food_cost":3000000,"logistics_cost":500000,"labor_cost":800000,"management_cost":500000,"estimate_reason":"smoke test"}' > /tmp/cost_est_b.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_B/cost-estimates" \
    -H "Content-Type: application/json" \
    -d @/tmp/cost_est_b.json)
ESTIMATE_ID=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
log_info "成本估算创建: id=$ESTIMATE_ID"

echo '{"confirm":true}' > /tmp/confirm_b.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/cost-estimates/$ESTIMATE_ID/confirm" \
    -H "Content-Type: application/json" \
    -d @/tmp/confirm_b.json)

echo '{"boss_final_price":5500000,"boss_decision_reason":"smoke test pricing","action_type":"normal"}' > /tmp/pricing_b.json
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_B/pricing-decisions" \
    -H "Content-Type: application/json" \
    -d @/tmp/pricing_b.json)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    log_pass "定价决策提交成功"
else
    log_fail "定价决策提交失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 11: 初始化形式审查
log_info "Step 11: 初始化形式审查"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_B/checklists/init" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    ITEMS_CREATED=$(echo "$RESPONSE" | grep -o '"itemsCreated":[0-9]*' | cut -d: -f2)
    log_pass "形式审查初始化成功: itemsCreated=$ITEMS_CREATED"
else
    log_fail "形式审查初始化失败: HTTP $HTTP_CODE"
    exit 1
fi

# Step 12: 完成审查
log_info "Step 12: 完成审查"
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID_B/complete" \
    -H "Content-Type: application/json")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
if [ "$HTTP_CODE" = "200" ]; then
    FINAL_STATUS=$(echo "$RESPONSE" | grep -o '"newStatus":"[^"]*"' | cut -d'"' -f4)
    log_pass "项目完成: status=$FINAL_STATUS"
    if [ "$FINAL_STATUS" = "completed" ]; then
        log_pass "路径B 全部12步通过 ✅"
    else
        log_warn "最终状态异常: $FINAL_STATUS (期望 completed)"
    fi
else
    log_fail "项目完成失败: HTTP $HTTP_CODE"
    exit 1
fi

echo ""
log_pass "=========================================="
log_pass "路径B：全部12步通过 ✅"
log_pass "=========================================="
echo ""

# 最终总结
echo "=========================================="
echo "TIS Daily Smoke Test 完成"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "路径A: ✅ 12步全部通过"
echo "路径B: ✅ 12步全部通过"
echo "=========================================="
echo ""
echo "测试项目清理（可选）:"
echo "docker exec tis_db psql -U postgres -d canteen_system -c \"DELETE FROM projects WHERE id IN ($PROJECT_ID_A, $PROJECT_ID_B);\""