"""AssetImage model — maps asset_id + slot to stored image file."""

import uuid

from sqlalchemy import Column, String, ForeignKey, UniqueConstraint

from models.base import Base, TimestampMixin


class AssetImage(Base, TimestampMixin):
    __tablename__ = "asset_images"
    __table_args__ = (
        UniqueConstraint("asset_id", "slot_key", name="uq_asset_slot"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(String(36), nullable=False, index=True)
    asset_type = Column(String(20))  # character | location | prop | variant
    slot_key = Column(String(50))    # front_full | east | front ...
    storage_key = Column(String(512))  # assets/images/{uuid}.jpeg
