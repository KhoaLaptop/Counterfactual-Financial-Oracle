"""Report API routes"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Union
import json
import uuid

from app.core.database import get_db
from app.models.report import Report
from app.api.schemas.reports import ReportResponse, ReportSummary
from app.services.landing_ai_service import LandingAIService

router = APIRouter()


@router.post("/upload", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def upload_report(
    file: UploadFile = File(None),
    # These come from multipart/form-data, so we must declare them as Form fields
    json_data: str | None = Form(None),
    company_name: str | None = Form(None),
    fiscal_year: int | None = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a financial report (PDF or JSON)

    - **PDF**: Will be processed using Landing AI ADE
    - **JSON**: Can be FinancialReport format or raw Landing AI response
    """
    landing_service = LandingAIService()
    report_data = None

    try:
        if file and file.filename:
            print(f"Processing upload for file: {file.filename}")
            # Handle file upload (PDF or JSON)
            file_content = await file.read()

            if file.filename.endswith(".pdf"):
                # PDF file
                financial_report = landing_service.extract_from_pdf(file_content, file.filename)
                report_data = financial_report.model_dump()
            elif file.filename.endswith(".json"):
                # JSON file
                try:
                    json_obj = json.loads(file_content.decode("utf-8"))
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid JSON format",
                    )
                financial_report = landing_service.parse_json(json_obj)
                report_data = financial_report.model_dump()
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File must be a PDF or JSON",
                )

        elif json_data:
            # Handle JSON string from form data
            try:
                json_obj = json.loads(json_data)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format",
                )

            financial_report = landing_service.parse_json(json_obj)
            report_data = financial_report.model_dump()

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either file or json_data must be provided",
            )

        # Extract metadata
        pdf_metadata = {}
        if hasattr(financial_report, "pdf_metadata") and financial_report.pdf_metadata:
            pdf_metadata = financial_report.pdf_metadata.model_dump()

        # Try to extract company name from report if not provided
        # Try to extract company name from report if not provided
        if not company_name and file and file.filename:
            # Simple heuristic to extract from filename
            # Expected format: Company_FY23_Q1.pdf or Company_2023.pdf
            try:
                clean_name = file.filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
                parts = clean_name.split()
                
                # Guess company name (first part)
                if not company_name and parts:
                    company_name = parts[0]
                
                # Guess fiscal year
                if not fiscal_year:
                    import re
                    # Look for 20xx or FYxx
                    for part in parts:
                        # Match 2020-2029
                        if re.match(r'202[0-9]', part):
                            fiscal_year = int(part)
                            break
                        # Match FY23, FY24, etc.
                        if re.match(r'fy[0-9]{2}', part.lower()):
                            fiscal_year = 2000 + int(part.lower().replace('fy', ''))
                            break
            except Exception:
                pass

        # Create database record
        db_report = Report(
            company_name=company_name,
            fiscal_year=fiscal_year,
            report_data=report_data,
            pdf_metadata=pdf_metadata,
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        return ReportResponse(
            id=db_report.id,
            company_name=db_report.company_name,
            fiscal_year=db_report.fiscal_year,
            pdf_metadata=db_report.pdf_metadata,
            report_data=db_report.report_data,
            created_at=db_report.created_at,
            updated_at=db_report.updated_at,
        )

    except HTTPException:
        # Re-raise HTTP exceptions (e.g., 400 errors) without wrapping as 500
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing report: {str(e)}",
        )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get report by ID"""
    print(f"DEBUG: get_report called with ID: {report_id} (type: {type(report_id)})")
    report = db.query(Report).filter(Report.id == report_id).first()
    print(f"DEBUG: Query result: {report}")
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    return ReportResponse(
        id=report.id,
        company_name=report.company_name,
        fiscal_year=report.fiscal_year,
        pdf_metadata=report.pdf_metadata,
        report_data=report.report_data,
        created_at=report.created_at,
        updated_at=report.updated_at
    )


@router.get("/", response_model=list[ReportSummary])
async def list_reports(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all reports"""
    reports = db.query(Report).order_by(Report.created_at.desc()).offset(skip).limit(limit).all()
    return [
        ReportSummary(
            id=r.id,
            company_name=r.company_name,
            fiscal_year=r.fiscal_year,
            created_at=r.created_at
        )
        for r in reports
    ]


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Delete a report and its related scenarios"""
    from app.models.scenario import Scenario
    
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Delete related scenarios first (SQLite doesn't enforce CASCADE)
    db.query(Scenario).filter(Scenario.report_id == report_id).delete()
    
    db.delete(report)
    db.commit()
    return None


