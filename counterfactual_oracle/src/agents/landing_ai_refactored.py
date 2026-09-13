"""
Refactored Landing AI Client using new modular architecture.
This replaces the monolithic landing_ai.py with clean separation of concerns.
"""

from typing import Dict, Any

from ..models import FinancialReport
from ..infrastructure.logging import get_logger
from ..infrastructure.security import FileValidationError
from ..parsers.extractor import DocumentExtractor
from ..parsers.mapper import FinancialMapper
from ..parsers.validator import ExtractionValidator

logger = get_logger(__name__)


class LandingAIClient:
    """
    Client for extracting financial data from PDF documents.
    Orchestrates extraction, mapping, and validation.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the client.
        
        Args:
            api_key: Landing AI API key (optional, will use settings if not provided)
        """
        self.extractor = DocumentExtractor()
        self.mapper = FinancialMapper()
        self.validator = ExtractionValidator()
    
    def extract_data(self, pdf_path: str) -> FinancialReport:
        """
        Extract financial data from PDF with full validation.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Validated FinancialReport
            
        Raises:
            FileValidationError: If file validation fails
            Exception: If extraction fails
        """
        logger.info("starting_extraction", pdf_path=pdf_path)
        
        # Step 1: Extract raw data
        raw_data = self.extractor.extract(pdf_path)
        
        # Step 2: Map to financial report
        report = self.mapper.parse_raw_response(raw_data)
        
        # Step 3: Validate
        validation = self.validator.validate(report)
        
        if not validation.is_valid:
            errors = validation.get_errors()
            error_msg = "; ".join([f"{e.field}: {e.message}" for e in errors])
            logger.error("validation_failed", errors=error_msg)
            raise FileValidationError(f"Extracted data validation failed: {error_msg}")
        
        # Log warnings
        for warning in validation.get_warnings():
            logger.warning(
                "validation_warning",
                field=warning.field,
                message=warning.message
            )
        
        logger.info(
            "extraction_successful",
            revenue=report.income_statement.Revenue,
            ebitda=report.income_statement.EBITDA,
            validation_issues=len(validation.issues)
        )
        
        return report
    
    def parse_landing_ai_response(self, raw_data: Dict[str, Any]) -> FinancialReport:
        """
        Parse pre-existing Landing AI response (for JSON uploads).
        
        Args:
            raw_data: Raw Landing AI response JSON
            
        Returns:
            FinancialReport
        """
        return self.mapper.parse_raw_response(raw_data)
