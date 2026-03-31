"""LLM-based qualification requirement extraction from tender PDF text."""
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# The LLM factory — same pattern as week3_rag
from app.core.week3_rag.llm_mock import get_llm


def decode_simsun_text(text: str) -> str:
    """
    Placeholder for SimSun font garbling fix.

    For the 惠州交通运输局招标文件, PyMuPDF already returns correctly
    decoded UTF-8 Chinese text, so no correction is needed.
    Kept as a hook for future PDFs with different font encoding issues.
    """
    return text


QUALIFICATION_EXTRACTION_PROMPT = """你是一个资深投标法务专家。你的任务是从这份招标文件中，穷尽式地提取出所有可能导致废标的硬性准入资质要求。

请严格按以下 4 个维度进行交叉扫描，严禁遗漏：

【基础法定资质】：政采项目提取《政府采购法》第二十二条要求；如出现"某部"、"部队"等军采字眼，强制提取军采特有资质（非外资控股声明、军队保密承诺等）。

【项目特定资格】：提取所有行业特许证明（如《食品经营许可证》）及特定政策要求（如面向中小微企业声明函）。

【实质性条款】：扫描全文，提取所有标注为"★"、"必须"、"否则视为无效投标"的硬性资质承诺。

【终极校验】：全局搜索并对齐文件中的"资格性审查表"、"符合性审查表"或"废标条款"。

## 输出格式

请严格输出纯 JSON，格式如下，绝对不要输出除此 JSON 之外的任何文字：

```json
{{
  "qualifications": [
    {{
      "type": "通用法定资质 | 军采特殊资质 | 行业特定资质 | 实质性承诺",
      "title": "资质简短名称（如：食品经营许可证）",
      "description": "详细要求描述",
      "source_section": "文件出处（如：资格审查表）"
    }}
  ],
  "is_military_procurement": true/false
}}
```

## 招标文件文本

```
{text}
```

请立即返回JSON：
"""


def extract_qualifications_with_llm(pdf_text: str, project_name: str = "") -> list[dict[str, Any]]:
    """
    Use DeepSeek LLM to extract qualification requirements from tender PDF text.

    Args:
        pdf_text: Full text extracted from the tender PDF document.
        project_name: Optional project name for context in logging.

    Returns:
        List of qualification requirement dicts.

    Raises:
        RuntimeError: If the API call fails or returns unparseable response.
    """
    decoded_text = decode_simsun_text(pdf_text)
    truncated_text = decoded_text[:12000]
    prompt = QUALIFICATION_EXTRACTION_PROMPT.format(text=truncated_text)

    llm = get_llm()

    logger.info(
        f"Calling DeepSeek LLM for qualification extraction "
        f"(project='{project_name}', text_len={len(truncated_text)}, mock={'Mock' if 'Mock' in type(llm).__name__ else 'Real'})"
    )

    response = llm.generate(
        prompt=prompt,
        mode="auto",
        temperature=0.2,
        max_tokens=2048,
    )

    content = response.content.strip()
    logger.info(f"LLM qualification extraction response (first 300 chars): {content[:300]}")

    # Parse JSON from response — may be wrapped in ```json ... ```
    json_str = content
    if content.startswith("```"):
        lines = content.split("\n")
        json_lines = [l for l in lines[1:-1] if not l.startswith("```")]
        json_str = "\n".join(json_lines)

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON response: {e}")
        logger.error(f"Response content: {content[:500]}")
        raise RuntimeError(
            f"LLM returned unparseable JSON for qualification extraction: {e}"
        ) from e

    # Normalize to list of {cert_code, cert_name, is_mandatory, ...} for downstream compatibility
    qualifications_raw = result.get("qualifications", [])
    validated = []
    for item in qualifications_raw:
        if not isinstance(item, dict):
            continue
        title = item.get("title", "") or item.get("cert_name", "")
        qtype = item.get("type", "通用法定资质")
        # Downstream expects cert_code; derive from type if absent
        cert_code = _type_to_code(qtype, title)
        validated.append({
            "cert_code": cert_code,
            "cert_name": title,
            "description": item.get("description", ""),
            "source_section": item.get("source_section", ""),
            "type": qtype,
            "is_mandatory": True,
        })

    logger.info(f"LLM extracted {len(validated)} qualification requirements (is_military={result.get('is_military_procurement', False)})")
    for q in validated:
        logger.info(f"  - [{q['type']}] {q['cert_name']}: {q['description'][:50]}")

    return validated


def _type_to_code(qtype: str, title: str) -> str:
    """Map the 4-type classification to cert_code for backward compatibility."""
    t = qtype.strip()
    if "军采" in t or "外资" in t or "保密" in t:
        return "MILITARY_SPECIAL"
    if "实质性" in t or "★" in title:
        return "SUBSTANTIAL_CLAUSE"
    if "食品" in title or "卫生" in title:
        return "FOOD_OPERATION_LICENSE"
    if "营业" in title:
        return "BUSINESS_LICENSE"
    if "质量" in title or "ISO" in title.upper():
        return "ISO_9001"
    return "OTHER_CERT"
