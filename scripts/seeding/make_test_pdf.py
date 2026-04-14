"""Create a test PDF for seeding pipeline smoke test."""
import sys
sys.path.insert(0, '/app')

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Frame
import io

# Try to use a Chinese font; fall back to built-in Helvetica
try:
    pdfmetrics.registerFont(TTFont('SimHei', '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc'))
    FONT = 'SimHei'
except Exception:
    FONT = 'Helvetica'

def create_tender_pdf(path):
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    def write(text, x=50, y=None, size=12):
        if y is None:
            y = current_y
        c.setFont(FONT, size)
        c.drawString(x, y, text)
        return y - 20

    current_y = height - 50

    # Title
    current_y = write("食堂物料配送服务项目招标文件", 150, current_y, 16)
    current_y = write("项目编号: CG-2024-001", 50, current_y, 10)
    current_y = write("预算金额: 人民币500万元", 50, current_y, 10)
    current_y = write("招标方式: 公开招标", 50, current_y, 10)
    current_y -= 20

    current_y = write("一、服务方案", 50, current_y, 13)
    lines = [
        "投标人应提供完整的服务方案，包括服务目标、服务承诺、质量保障措施、",
        "应急处理预案等内容。服务方案应体现投标人对本项目的理解深度和差异",
        "化竞争优势。投标人需承诺在合同期内严格按照食品安全法和相关法规",
        "操作，确保食材来源可追溯，全程冷链配送。食材溯源和冷链管理是重",
        "要评分指标。服务方案需要详细说明配送网络、应急预案、质量追溯体系。",
    ]
    for line in lines:
        current_y = write(line, 60, current_y, 10)

    current_y -= 15
    current_y = write("二、评分标准", 50, current_y, 13)
    lines2 = [
        "本项目采用综合评分法，总分100分，其中技术评分占60%，价格评分占40%。",
        "技术评分标准包括企业资质10分、服务方案20分、食材溯源10分、冷链管理",
        "10分、历史业绩10分。价格评分采用低价优先原则。评分包括十个维度，",
        "每个维度均有明确的评分细则和分值权重。技术分和商务分分开统计。",
    ]
    for line in lines2:
        current_y = write(line, 60, current_y, 10)

    current_y -= 15
    current_y = write("三、冷链管理", 50, current_y, 13)
    lines3 = [
        "投标人必须具备完善的冷链配送体系，冷链车需配备温度监控系统，",
        "实现全程温度记录和追溯。冷库需符合食品安全标准，温度控制在",
        "0-8摄氏度之间。冷链配送是核心竞争要素，需要详细说明冷藏车数量、",
        "温控设备配置、全程冷链保障措施。配送时效要求在24小时内完成。",
    ]
    for line in lines3:
        current_y = write(line, 60, current_y, 10)

    current_y -= 15
    current_y = write("四、报价文件", 50, current_y, 13)
    lines4 = [
        "投标人需按招标文件要求的格式填报报价，包括单价、总价及分项报价。",
        "预算金额为人民币500万元，报价不得超过预算。报价需包含运输费、",
        "配送费、卸货费及其他费用。价格合理性是重要评标因素。",
    ]
    for line in lines4:
        current_y = write(line, 60, current_y, 10)

    current_y -= 15
    current_y = write("五、企业资质", 50, current_y, 13)
    lines5 = [
        "投标人应具有有效的营业执照、食品经营许可证、ISO9001质量管理体系",
        "认证、ISO22000食品安全管理体系认证等资质证书。",
    ]
    for line in lines5:
        current_y = write(line, 60, current_y, 10)

    current_y -= 15
    current_y = write("六、历史业绩", 50, current_y, 13)
    lines6 = [
        "投标人需提供近三年内同类项目成功案例不少于3个，单项合同金额不",
        "低于100万元。需要提供合同复印件、用户验收报告等证明材料。",
    ]
    for line in lines6:
        current_y = write(line, 60, current_y, 10)

    c.save()
    print(f"PDF saved: {path} ({len(open(path,'rb').read())} bytes)")

if __name__ == "__main__":
    import os
    os.makedirs("/tmp/historical_documents", exist_ok=True)
    create_tender_pdf("/tmp/historical_documents/食堂配送服务项目招标文件.pdf")
