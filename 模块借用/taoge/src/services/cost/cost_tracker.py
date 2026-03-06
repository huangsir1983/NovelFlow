"""
涛割 - 成本追踪服务
负责积分消耗记录、余额管理、预警和报表
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, pyqtSignal

from database.session import session_scope
from database.models import CostRecord, CostSummary
from config.settings import SettingsManager


class CostTracker(QObject):
    """
    成本追踪器
    记录每次操作的积分消耗，提供余额查询、预警和报表
    """

    # 信号定义
    credits_deducted = pyqtSignal(float, float)  # amount, remaining
    credits_warning = pyqtSignal(float)  # remaining
    credits_exhausted = pyqtSignal()  # 积分耗尽
    record_created = pyqtSignal(int)  # record_id

    _instance: Optional['CostTracker'] = None

    def __init__(self):
        super().__init__()
        self._settings = SettingsManager()

    @property
    def balance(self) -> float:
        """当前积分余额"""
        return self._settings.settings.credits.balance

    @property
    def cost_config(self) -> Dict[str, float]:
        """各操作单次成本配置"""
        return self._settings.settings.credits.cost_per_call

    # ==================== 积分操作 ====================

    def deduct(self, operation_type: str, model_used: str = None,
               project_id: int = None, task_id: int = None,
               amount: float = None, notes: str = None) -> bool:
        """
        扣除积分并记录

        Args:
            operation_type: 操作类型 (image_gen, video_gen, tag_gen, etc.)
            model_used: 使用的模型名称
            project_id: 关联的项目ID
            task_id: 关联的任务ID
            amount: 自定义扣除金额（为None时使用配置）
            notes: 备注

        Returns:
            是否成功扣除
        """
        if amount is None:
            cost_key = self._get_cost_key(operation_type, model_used)
            amount = self.cost_config.get(cost_key, 0.0)

        if amount <= 0:
            return True

        credits_before = self.balance

        if credits_before < amount:
            self.credits_exhausted.emit()
            return False

        # 扣除积分
        success = self._settings.deduct_credits(operation_type, amount)
        if not success:
            return False

        credits_after = self.balance

        # 创建记录
        self._create_record(
            operation_type=operation_type,
            operation_name=self._get_operation_name(operation_type),
            model_used=model_used,
            credits_used=amount,
            credits_before=credits_before,
            credits_after=credits_after,
            project_id=project_id,
            task_id=task_id,
            notes=notes,
        )

        self.credits_deducted.emit(amount, credits_after)

        # 检查预警
        self._check_warning()

        return True

    def estimate_cost(self, operation_type: str, model_used: str = None,
                      count: int = 1) -> float:
        """
        预估操作成本

        Args:
            operation_type: 操作类型
            model_used: 使用的模型
            count: 操作次数

        Returns:
            预估总成本
        """
        cost_key = self._get_cost_key(operation_type, model_used)
        unit_cost = self.cost_config.get(cost_key, 0.0)
        return unit_cost * count

    def can_afford(self, operation_type: str, model_used: str = None,
                   count: int = 1) -> bool:
        """检查是否有足够积分"""
        estimated = self.estimate_cost(operation_type, model_used, count)
        return self.balance >= estimated

    def get_remaining(self) -> float:
        """获取剩余积分"""
        return self.balance

    # ==================== 记录管理 ====================

    def _create_record(self, operation_type: str, operation_name: str,
                       model_used: str, credits_used: float,
                       credits_before: float, credits_after: float,
                       project_id: int = None, task_id: int = None,
                       notes: str = None) -> Optional[int]:
        """创建成本记录"""
        try:
            with session_scope() as session:
                record = CostRecord(
                    project_id=project_id,
                    task_id=task_id,
                    operation_type=operation_type,
                    operation_name=operation_name,
                    model_used=model_used,
                    credits_used=credits_used,
                    credits_before=credits_before,
                    credits_after=credits_after,
                    notes=notes,
                )
                session.add(record)
                session.flush()

                record_id = record.id
                self.record_created.emit(record_id)
                return record_id

        except Exception as e:
            print(f"创建成本记录失败: {e}")
            return None

    def get_records(self, project_id: int = None,
                    operation_type: str = None,
                    days: int = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取成本记录

        Args:
            project_id: 按项目筛选
            operation_type: 按操作类型筛选
            days: 最近N天
            limit: 返回数量限制

        Returns:
            记录字典列表
        """
        try:
            with session_scope() as session:
                query = session.query(CostRecord)

                if project_id is not None:
                    query = query.filter(CostRecord.project_id == project_id)

                if operation_type:
                    query = query.filter(CostRecord.operation_type == operation_type)

                if days:
                    since = datetime.now() - timedelta(days=days)
                    query = query.filter(CostRecord.created_at >= since)

                query = query.order_by(CostRecord.created_at.desc())
                query = query.limit(limit)

                records = query.all()
                return [r.to_dict() for r in records]

        except Exception as e:
            print(f"获取成本记录失败: {e}")
            return []

    # ==================== 报表与统计 ====================

    def get_summary(self, project_id: int = None,
                    days: int = None) -> Dict[str, Any]:
        """
        获取成本汇总

        Args:
            project_id: 按项目筛选
            days: 最近N天

        Returns:
            汇总字典
        """
        try:
            with session_scope() as session:
                query = session.query(CostRecord)

                if project_id is not None:
                    query = query.filter(CostRecord.project_id == project_id)

                if days:
                    since = datetime.now() - timedelta(days=days)
                    query = query.filter(CostRecord.created_at >= since)

                records = query.all()

                summary = CostSummary(project_id=project_id)
                for record in records:
                    summary.add_record(record)

                result = summary.to_dict()
                result['current_balance'] = self.balance
                result['usage_ratio'] = self._get_usage_ratio()

                return result

        except Exception as e:
            print(f"获取成本汇总失败: {e}")
            return {
                'total_credits_used': 0,
                'credits_by_operation': {},
                'credits_by_model': {},
                'records_count': 0,
                'current_balance': self.balance,
                'usage_ratio': 0,
            }

    def get_project_cost(self, project_id: int) -> float:
        """获取项目总成本"""
        try:
            with session_scope() as session:
                from sqlalchemy import func
                result = session.query(
                    func.sum(CostRecord.credits_used)
                ).filter(
                    CostRecord.project_id == project_id
                ).scalar()
                return result or 0.0

        except Exception as e:
            print(f"获取项目成本失败: {e}")
            return 0.0

    def get_daily_costs(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取每日成本统计

        Args:
            days: 最近N天

        Returns:
            每日成本列表 [{'date': '2026-02-06', 'total': 50.0, 'count': 10}, ...]
        """
        try:
            with session_scope() as session:
                from sqlalchemy import func, cast, Date
                since = datetime.now() - timedelta(days=days)

                results = session.query(
                    func.date(CostRecord.created_at).label('date'),
                    func.sum(CostRecord.credits_used).label('total'),
                    func.count(CostRecord.id).label('count')
                ).filter(
                    CostRecord.created_at >= since
                ).group_by(
                    func.date(CostRecord.created_at)
                ).order_by(
                    func.date(CostRecord.created_at)
                ).all()

                return [
                    {
                        'date': str(r.date),
                        'total': r.total or 0.0,
                        'count': r.count or 0,
                    }
                    for r in results
                ]

        except Exception as e:
            print(f"获取每日成本失败: {e}")
            return []

    # ==================== 预警机制 ====================

    def _check_warning(self):
        """检查积分预警"""
        ratio = self._get_usage_ratio()
        threshold = self._settings.settings.credits.warning_threshold

        if ratio >= self._settings.settings.credits.auto_stop_threshold:
            self.credits_exhausted.emit()
        elif ratio >= threshold:
            self.credits_warning.emit(self.balance)

    def _get_usage_ratio(self) -> float:
        """获取积分使用比例"""
        initial = 1000.0  # 初始积分
        used = initial - self.balance
        return max(0.0, min(1.0, used / initial)) if initial > 0 else 0.0

    def is_warning(self) -> bool:
        """当前是否处于预警状态"""
        ratio = self._get_usage_ratio()
        return ratio >= self._settings.settings.credits.warning_threshold

    # ==================== 工具方法 ====================

    def _get_cost_key(self, operation_type: str, model_used: str = None) -> str:
        """构造成本配置键"""
        if model_used:
            key = f"{model_used}_{operation_type}"
            if key in self.cost_config:
                return key

        # 通用映射
        type_mapping = {
            'image_gen': 'vidu_image',
            'video_gen': 'vidu_video',
            'i2v': 'vidu_video',
            'tag_gen': 'deepseek_text',
        }
        return type_mapping.get(operation_type, operation_type)

    @staticmethod
    def _get_operation_name(operation_type: str) -> str:
        """获取操作显示名称"""
        names = {
            'image_gen': '图像生成',
            'video_gen': '视频生成',
            'i2v': '图生视频',
            'tag_gen': 'AI标签生成',
            'comfyui_workflow': 'ComfyUI工作流',
        }
        return names.get(operation_type, operation_type)


# 便捷函数
def get_cost_tracker() -> CostTracker:
    """获取成本追踪器单例"""
    return CostTracker()
