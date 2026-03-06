"""
涛割 - 任务数据模型
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class Task(Base):
    """任务模型 - 用于异步任务队列管理"""
    __tablename__ = 'tasks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    scene_id = Column(Integer, ForeignKey('scenes.id'), nullable=True)

    # 任务信息
    task_type = Column(String(50), nullable=False)  # image_gen, video_gen, tag_gen, export
    task_name = Column(String(255), nullable=True)
    priority = Column(Integer, default=5)  # 1-10, 数字越小优先级越高

    # 状态
    status = Column(String(50), default="pending")  # pending, queued, running, completed, failed, cancelled
    progress = Column(Float, default=0.0)  # 0-100
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # 输入输出
    input_data = Column(JSON, default=dict)  # 任务输入参数
    output_data = Column(JSON, default=dict)  # 任务输出结果
    result_path = Column(String(512), nullable=True)  # 结果文件路径

    # 模型和成本
    model_used = Column(String(50), nullable=True)
    estimated_cost = Column(Float, default=0.0)
    actual_cost = Column(Float, default=0.0)

    # 时间信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 外部API信息
    external_task_id = Column(String(255), nullable=True)  # 外部API返回的任务ID
    external_status = Column(String(50), nullable=True)

    # 关联关系
    project = relationship("Project", back_populates="tasks")

    def __repr__(self):
        return f"<Task(id={self.id}, type='{self.task_type}', status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'scene_id': self.scene_id,
            'task_type': self.task_type,
            'task_name': self.task_name,
            'priority': self.priority,
            'status': self.status,
            'progress': self.progress,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'model_used': self.model_used,
            'estimated_cost': self.estimated_cost,
            'actual_cost': self.actual_cost,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    @property
    def duration(self) -> float:
        """计算任务执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    @property
    def is_retryable(self) -> bool:
        """判断任务是否可重试"""
        return self.status == 'failed' and self.retry_count < self.max_retries
