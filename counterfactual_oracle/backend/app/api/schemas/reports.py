"""Pydantic schemas for report API"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime


class ReportCreate(BaseModel):
    """Request schema for creating a report"""
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None


class ReportResponse(BaseModel):
    """Response schema for report"""
    id: UUID
    company_name: Optional[str]
    fiscal_year: Optional[int]
    pdf_metadata: Optional[Dict[str, Any]]
    report_data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ReportSummary(BaseModel):
    """Summary schema for report (lightweight)"""
    id: UUID
    company_name: Optional[str]
    fiscal_year: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


