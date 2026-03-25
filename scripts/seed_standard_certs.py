#!/usr/bin/env python3
"""Seed standard certifications data."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.standard import StandardCertification
from app.dependencies import get_db
import json

# Seed data for 5 standard certifications
SEED_DATA = [
    {
        'cert_code': 'BUSINESS-LICENSE',
        'cert_full_name': '营业执照',
        'cert_short_name': '营业执照',
        'aliases': ['营业执照', '公司营业执照', '企业营业执照'],
        'required_keywords': ['营业执照'],
        'exclude_keywords': ['副本', '吊销'],
        'cert_number_pattern': r'^([0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10})$',
        'issuing_authority_keywords': ['市场监督管理局', '工商行政管理局'],
        'category': 'enterprise',
        'validity_years': None,
        'is_mandatory_for_food_delivery': True,
        'is_mandatory_for_property': True,
        'is_active': True,
    },
    {
        'cert_code': 'FOOD-BUSINESS-LICENSE',
        'cert_full_name': '食品经营许可证',
        'cert_short_name': '食品经营许可证',
        'aliases': ['食品经营许可证', '食品流通许可证', '食品经营'],
        'required_keywords': ['食品经营', '许可证'],
        'exclude_keywords': ['生产', '小作坊'],
        'cert_number_pattern': r'^([0-9A-Z]{14})$',
        'issuing_authority_keywords': ['市场监督管理局', '食品药品监督管理局'],
        'category': 'food',
        'validity_years': 5,
        'is_mandatory_for_food_delivery': True,
        'is_mandatory_for_property': False,
        'is_active': True,
    },
    {
        'cert_code': 'ISO-9001-2015',
        'cert_full_name': '质量管理体系认证',
        'cert_short_name': 'ISO9001',
        'aliases': ['ISO9001', 'ISO 9001', '质量体系认证', '质量管理体系认证'],
        'required_keywords': ['质量管理体系', '认证'],
        'exclude_keywords': ['环境', '职业健康'],
        'cert_number_pattern': None,
        'issuing_authority_keywords': ['认证认可监督管理委员会', '方圆标志认证集团'],
        'category': 'iso',
        'validity_years': 3,
        'is_mandatory_for_food_delivery': False,
        'is_mandatory_for_property': True,
        'is_active': True,
    },
    {
        'cert_code': 'ISO-14001-2015',
        'cert_full_name': '环境管理体系认证',
        'cert_short_name': 'ISO14001',
        'aliases': ['ISO14001', 'ISO 14001', '环境体系认证', '环境管理体系认证'],
        'required_keywords': ['环境管理体系', '认证'],
        'exclude_keywords': ['质量', '职业健康'],
        'cert_number_pattern': None,
        'issuing_authority_keywords': ['认证认可监督管理委员会', '华夏认证中心'],
        'category': 'iso',
        'validity_years': 3,
        'is_mandatory_for_food_delivery': False,
        'is_mandatory_for_property': True,
        'is_active': True,
    },
    {
        'cert_code': 'HACCP',
        'cert_full_name': '危害分析与关键控制点体系认证',
        'cert_short_name': 'HACCP',
        'aliases': ['HACCP认证', 'HACCP', '食品安全管理体系', '危害分析与关键控制点'],
        'required_keywords': ['危害分析', '关键控制点'],
        'exclude_keywords': ['ISO9001', 'ISO22000'],
        'cert_number_pattern': None,
        'issuing_authority_keywords': ['认证认可监督管理委员会', '中国食品药品检定研究院'],
        'category': 'food',
        'validity_years': 3,
        'is_mandatory_for_food_delivery': True,
        'is_mandatory_for_property': False,
        'is_active': True,
    },
]


def seed_to_database(db):
    """Seed the standard certifications into the database."""
    seeded_count = 0
    for data in SEED_DATA:
        cert = db.query(StandardCertification).filter_by(cert_code=data['cert_code']).first()
        if not cert:
            cert = StandardCertification(**data)
            db.add(cert)
            seeded_count += 1
    db.commit()
    return seeded_count


def main():
    """Main entry point for seeding."""
    db = next(get_db())
    try:
        seeded_count = seed_to_database(db)
        print(f"Seeded {seeded_count} standard certifications (total: {len(SEED_DATA)})")
    finally:
        db.close()


if __name__ == '__main__':
    main()
