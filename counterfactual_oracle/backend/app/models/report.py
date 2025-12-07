"""Report database model"""
from sqlalchemy import Column, String, Integer, JSON, DateTime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.core.database import Base, GUID


class Report(Base):
    """Financial report database model"""
    __tablename__ = "reports"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(255), nullable=True)
    fiscal_year = Column(Integer, nullable=True)
    report_data = Column(JSON, nullable=False)  # Full FinancialReport JSON
    pdf_metadata = Column(JSON, nullable=True)  # PDF metadata, extraction info (renamed from 'metadata' - SQLAlchemy reserved)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


