"""
涛割 - 成本记录数据模型
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base


class CostRecord(Base):
    """成本记录模型 - 用于积分追踪"""
    __tablename__ = 'cost_records'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=True)

    # 操作信息
    operation_type = Column(String(50), nullable=False)  # image_gen, video_gen, tag_gen, etc.
    operation_name = Column(String(255), nullable=True)
    model_used = Column(String(50), nullable=True)

    # 成本信息
    credits_used = Column(Float, default=0.0)  # 消耗的积分
    credits_before = Column(Float, default=0.0)  # 操作前积分
    credits_after = Column(Float, default=0.0)  # 操作后积分

    # 详情
    details = Column(JSON, default=dict)  # 额外详细信息
    notes = Column(Text, nullable=True)

    # 时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关联关系
    project = relationship("Project", back_populates="costs")

    def __repr__(self):
        return f"<CostRecord(id={self.id}, type='{self.operation_type}', credits={self.credits_used})>"

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'task_id': self.task_id,
            'operation_type': self.operation_type,
            'operation_name': self.operation_name,
            'model_used': self.model_used,
            'credits_used': self.credits_used,
            'credits_before': self.credits_before,
            'credits_after': self.credits_after,
            'details': self.details,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class CostSummary:
    """成本汇总（非ORM，用于报表）"""

    def __init__(self, project_id: int = None):
        self.project_id = project_id
        self.total_credits_used = 0.0
        self.credits_by_operation = {}
        self.credits_by_model = {}
        self.records_count = 0

    def add_record(self, record: CostRecord):
        self.total_credits_used += record.credits_used
        self.records_count += 1

        # 按操作类型统计
        op_type = record.operation_type
        if op_type not in self.credits_by_operation:
            self.credits_by_operation[op_type] = 0.0
        self.credits_by_operation[op_type] += record.credits_used

        # 按模型统计
        model = record.model_used or "unknown"
        if model not in self.credits_by_model:
            self.credits_by_model[model] = 0.0
        self.credits_by_model[model] += record.credits_used

    def to_dict(self):
        return {
            'project_id': self.project_id,
            'total_credits_used': self.total_credits_used,
            'credits_by_operation': self.credits_by_operation,
            'credits_by_model': self.credits_by_model,
            'records_count': self.records_count,
        }
