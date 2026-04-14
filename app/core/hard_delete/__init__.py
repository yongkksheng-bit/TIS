"""Hard Delete — 核心逻辑模块

三方联动清理：
1. PostgreSQL：级联删除项目主记录及所有关联行（TenderDocument、BidDocument 等）
2. MinIO：删除该项目所有归档文件对象
3. pgvector：删除该项目的所有知识向量片段

关键约束：
- MinIO/pgvector 失败不影响 DB 事务（两者为独立清理步骤）
- 删除向量数据时使用 project_id 精确过滤，严禁误删其他项目数据
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def hard_delete_project(db: Session, project_id: int) -> dict:
    """
    执行项目物理删除（永久销毁）。

    三方联动清理顺序：
    1. PostgreSQL：检查项目存在且已软删除，收集项目名
    2. MinIO：删除该项目所有归档文件对象（非阻塞）
    3. pgvector：删除 knowledge_chunks（非阻塞）
    4. PostgreSQL：先删无 CASCADE 子表，再删主记录（DB CASCADE 自动清理其余子表）

    Args:
        db: SQLAlchemy Session
        project_id: 要删除的项目 ID

    Returns:
        包含清理结果的字典：{project_id, project_name, minio_deleted, vector_deleted, db_deleted}

    Raises:
        ValueError: 项目不存在或未软删除（is_deleted != True）
    """
    from app.models.project import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError(f"项目 {project_id} 不存在")

    if not project.is_deleted:
        raise ValueError(
            f"项目 {project_id} ({project.project_name}) 未进入回收站，必须先执行软删除才能永久销毁"
        )

    project_name = project.project_name
    result = {
        "project_id": project_id,
        "project_name": project_name,
        "minio_deleted": 0,
        "vector_deleted": 0,
        "db_deleted": False,
    }

    # Step 2: MinIO 清理（失败不影响整体流程）
    try:
        from app.core.hard_delete.minio_cleanup import MinioCleanupService
        minio_svc = MinioCleanupService()
        deleted = minio_svc.delete_project_objects(project_id)
        result["minio_deleted"] = deleted if deleted >= 0 else 0
    except Exception as e:
        logger.error(f"MinIO cleanup failed for project {project_id}: {e}")
        result["minio_deleted"] = -1  # 表示失败但不阻塞

    # Step 3: pgvector 清理（删除 knowledge_chunks）
    try:
        from app.models.knowledge_chunk import KnowledgeChunk
        deleted_chunks = db.query(KnowledgeChunk).filter(
            KnowledgeChunk.source_project_id == project_id
        ).delete()
        result["vector_deleted"] = deleted_chunks
        logger.info(f"Deleted {deleted_chunks} knowledge_chunks for project {project_id}")
    except Exception as e:
        logger.error(f"pgvector cleanup failed for project {project_id}: {e}")
        result["vector_deleted"] = -1

    # Step 4: PostgreSQL 物理删除
    # 以下子表有 FK(project_id) 但数据库层无 ON DELETE CASCADE，需先手动删除
    try:
        from app.models.approval import ApprovalLog
        from app.models.discarded import DiscardedProject
        deleted_logs = db.query(ApprovalLog).filter(
            ApprovalLog.project_id == project_id
        ).delete()
        logger.info(f"Deleted {deleted_logs} approval_logs for project {project_id}")
        deleted_discarded = db.query(DiscardedProject).filter(
            DiscardedProject.project_id == project_id
        ).delete()
        logger.info(f"Deleted {deleted_discarded} discarded_projects for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to delete child records for project {project_id}: {e}")

    # 主记录删除（带 CASCADE 的子表由 DB 层自动清理）
    db.delete(project)
    db.commit()
    result["db_deleted"] = True
    logger.info(f"Hard deleted project {project_id} ({project_name}) from PostgreSQL")

    return result
