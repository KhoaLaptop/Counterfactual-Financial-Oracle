"""Scenario API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from app.core.database import get_db
from app.models.report import Report
from app.models.scenario import Scenario
from app.api.schemas.scenarios import ScenarioCreate, ScenarioResponse, ScenarioStatus
from app.services.simulation_service import SimulationService
from app.services.agents_service import AgentsService
from app.services.report_service import ReportService
from app.domain.models import FinancialReport, ScenarioParams

router = APIRouter()


def execute_scenario_task(
    scenario_id: uuid.UUID,
    report_data: dict,
    params: dict
):
    """Background task to execute scenario analysis"""
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if not scenario:
            return
        
        # Update status to RUNNING
        scenario.status = "RUNNING"
        scenario.progress = 10
        db.commit()
        
        try:
            # Reconstruct FinancialReport from JSON
            financial_report = FinancialReport(**report_data)
            scenario_params = ScenarioParams(**params)
            
            # Initialize services
            simulation_service = SimulationService()
            agents_service = AgentsService()

            # Step 1: Run Monte Carlo simulation
            scenario.progress = 30
            db.commit()
            
            simulation_results = simulation_service.run_simulation(
                financial_report, 
                scenario_params
            )
            
            # Step 2: Run critic
            scenario.progress = 50
            db.commit()
            
            critic_verdict = agents_service.critique(
                financial_report,
                simulation_results
            )
            
            # Step 3: Run debate
            scenario.progress = 70
            db.commit()
            
            debate_result = agents_service.run_debate(
                financial_report,
                simulation_results,
                scenario_params,
                max_rounds=10
            )
            
            # Step 4: Determine final verdict
            final_verdict = debate_result.final_verdict
            
            # Update scenario with results
            scenario.status = "COMPLETED"
            scenario.progress = 100
            scenario.simulation_results = simulation_results.model_dump()
            scenario.critic_verdict = critic_verdict.model_dump()
            scenario.debate_result = debate_result.model_dump()
            scenario.final_verdict = final_verdict
            scenario.updated_at = datetime.utcnow()
            
            db.commit()
            
        except Exception as e:
            # Mark as failed
            scenario.status = "FAILED"
            scenario.error_message = str(e)
            scenario.progress = 0
            db.commit()
            # Log the error
            print(f"Error executing scenario {scenario_id}: {str(e)}")
        
    finally:
        db.close()


@router.post("/", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
async def create_scenario(
    scenario_data: ScenarioCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new scenario and trigger background analysis"""
    # Verify report exists
    report = db.query(Report).filter(Report.id == scenario_data.report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Create scenario params
    params = {
        "revenue_growth_delta_bps": scenario_data.revenue_growth_delta_bps,
        "opex_delta_bps": scenario_data.opex_delta_bps,
        "discount_rate_delta_bps": scenario_data.discount_rate_delta_bps,
        "tax_rate_delta_bps": scenario_data.tax_rate_delta_bps
    }
    
    # Create scenario record
    scenario = Scenario(
        report_id=scenario_data.report_id,
        name=scenario_data.name,
        status="PENDING",
        params=params,
        progress=0
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    
    # Trigger background task
    background_tasks.add_task(
        execute_scenario_task,
        scenario.id,
        report.report_data,
        params
    )
    
    return ScenarioResponse(
        id=scenario.id,
        report_id=scenario.report_id,
        name=scenario.name,
        status=scenario.status,
        params=scenario.params,
        simulation_results=scenario.simulation_results,
        critic_verdict=scenario.critic_verdict,
        debate_result=scenario.debate_result,
        final_verdict=scenario.final_verdict,
        error_message=scenario.error_message,
        progress=scenario.progress,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at
    )


@router.get("/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get full scenario details"""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    return ScenarioResponse(
        id=scenario.id,
        report_id=scenario.report_id,
        name=scenario.name,
        status=scenario.status,
        params=scenario.params,
        simulation_results=scenario.simulation_results,
        critic_verdict=scenario.critic_verdict,
        debate_result=scenario.debate_result,
        final_verdict=scenario.final_verdict,
        error_message=scenario.error_message,
        progress=scenario.progress,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at
    )


@router.get("/{scenario_id}/status", response_model=ScenarioStatus)
async def get_scenario_status(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get lightweight scenario status for polling"""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    return ScenarioStatus(
        id=scenario.id,
        status=scenario.status,
        progress=scenario.progress,
        error_message=scenario.error_message
    )


@router.get("/", response_model=list[ScenarioResponse])
async def list_scenarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all scenarios"""
    scenarios = db.query(Scenario).order_by(Scenario.created_at.desc()).offset(skip).limit(limit).all()
    return [
        ScenarioResponse(
            id=s.id,
            report_id=s.report_id,
            name=s.name,
            status=s.status,
            params=s.params,
            simulation_results=s.simulation_results,
            critic_verdict=s.critic_verdict,
            debate_result=s.debate_result,
            final_verdict=s.final_verdict,
            error_message=s.error_message,
            progress=s.progress,
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        for s in scenarios
    ]


@router.post("/{scenario_id}/report")
async def generate_pdf_report(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Generate PDF report for completed scenario"""
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    if scenario.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scenario must be completed to generate report. Current status: {scenario.status}"
        )
    
    # Get report
    report = db.query(Report).filter(Report.id == scenario.report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Reconstruct models from JSON
    financial_report = FinancialReport(**report.report_data)
    from app.domain.models import AggregatedSimulation, CriticVerdict
    from app.domain.agents.debate_agent import DebateResult
    
    simulation = AggregatedSimulation(**scenario.simulation_results)
    critic_verdict = CriticVerdict(**scenario.critic_verdict)
    debate_result = DebateResult(**scenario.debate_result) if scenario.debate_result else None
    
    # Generate PDF
    report_service = ReportService()
    pdf_bytes = report_service.generate_pdf(
        simulation=simulation,
        critic_verdict=critic_verdict,
        report=financial_report,
        debate_result=debate_result
    )
    
    # Save to temporary file and return
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(pdf_bytes)
        tmp_path = tmp_file.name
    
    return FileResponse(
        tmp_path,
        media_type="application/pdf",
        filename=f"scenario_{scenario_id}_report.pdf"
    )



