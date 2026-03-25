import pytest
from pathlib import Path


@pytest.fixture
def check_tables_exist():
    """
    Fixture that checks if all Week 1 tables are created by the migration.

    Returns a function that checks if table creation statements exist in the migration.
    """
    def _check_tables(sql_output):
        expected_tables = [
            'CREATE TABLE projects',
            'CREATE TABLE standard_certifications',
            'CREATE TABLE tender_documents',
            'CREATE TABLE bid_documents',
            'CREATE TABLE document_images',
            'CREATE TABLE ocr_extractions',
        ]
        results = {}
        for table in expected_tables:
            results[table] = table.upper() in sql_output.upper()
        return results

    return _check_tables
