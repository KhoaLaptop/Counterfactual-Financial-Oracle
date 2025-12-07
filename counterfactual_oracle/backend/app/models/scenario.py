"""Scenario database model"""
from sqlalchemy import Column, String, Integer, JSON, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.core.database import Base, GUID


class Scenario(Base):
    """Scenario database model"""
    __tablename__ = "scenarios"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    report_id = Column(GUID(), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=True)
    status = Column(String(20), default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    params = Column(JSON, nullable=False)  # ScenarioParams JSON
    simulation_results = Column(JSON, nullable=True)  # AggregatedSimulation JSON
    critic_verdict = Column(JSON, nullable=True)  # CriticVerdict JSON
    debate_result = Column(JSON, nullable=True)  # DebateResult JSON
    final_verdict = Column(String(50), nullable=True)  # Buy/Hold/Sell
    error_message = Column(Text, nullable=True)
    progress = Column(Integer, default=0)  # 0-100 for progress tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship
    report = relationship("Report", backref="scenarios")



