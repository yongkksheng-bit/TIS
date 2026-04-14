"""Hard Delete — MinIO/S3 对象存储清理模块

在物理删除项目时，同步清理该项目的所有存储对象。
目前 PDF 文件存储在容器本地临时目录（见 projects.py upload_document），
但 MinIO 是未来归档文件的标准存储，此服务为未来的归档清理预留。

清理逻辑：
1. 根据 project_id 构造对象前缀（如 `project-{id}/`）
2. 列出所有匹配前缀的对象
3. 批量删除

MinIO 连接信息从 app.config.settings 读取（DATABASE_URL 同级配置）。
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Optional import — MinIO 客户端未安装时不阻塞其他清理流程
try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except ImportError:
    MINIO_AVAILABLE = False
    logger.warning("minio package not installed — MinIO cleanup will be skipped")


class MinioCleanupService:
    """清理指定项目在 MinIO 中存储的所有对象。"""

    BUCKET_NAME = "tis-project-files"

    def __init__(self):
        if not MINIO_AVAILABLE:
            return
        from app.config import settings
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,  # 本地 Docker 网络用 HTTP
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        """确保 bucket 存在，不存在则创建。"""
        try:
            if not self.client.bucket_exists(self.BUCKET_NAME):
                self.client.make_bucket(self.BUCKET_NAME)
                logger.info(f"Created MinIO bucket: {self.BUCKET_NAME}")
        except S3Error as e:
            logger.warning(f"MinIO bucket check/create failed: {e}")

    def list_project_objects(self, project_id: int) -> List[str]:
        """列出该项目所有存储对象路径。"""
        if not MINIO_AVAILABLE:
            return []
        prefix = f"project-{project_id}/"
        objects: List[str] = []
        try:
            for obj in self.client.list_objects(self.BUCKET_NAME, prefix=prefix, recursive=True):
                objects.append(obj.object_name)
        except S3Error as e:
            logger.warning(f"MinIO list objects failed for project {project_id}: {e}")
        return objects

    def delete_project_objects(self, project_id: int) -> int:
        """
        删除该项目的所有 MinIO 对象。

        Returns:
            删除的对象数量。失败时返回 -1。
        """
        if not MINIO_AVAILABLE:
            logger.info(f"MinIO not available — skipping cleanup for project {project_id}")
            return 0

        objects = self.list_project_objects(project_id)
        if not objects:
            logger.info(f"No MinIO objects found for project {project_id}")
            return 0

        try:
            # MinIO 批量删除每次最多 1000 个
            for i in range(0, len(objects), 1000):
                batch = objects[i:i + 1000]
                self.client.remove_objects(self.BUCKET_NAME, batch)
            logger.info(f"Deleted {len(objects)} MinIO objects for project {project_id}")
            return len(objects)
        except S3Error as e:
            logger.error(f"MinIO delete failed for project {project_id}: {e}")
            return -1

    def object_exists(self, project_id: int) -> bool:
        """检查该项目是否有任何存储对象。"""
        return len(self.list_project_objects(project_id)) > 0
