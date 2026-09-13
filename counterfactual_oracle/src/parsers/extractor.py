"""
Document extraction client for Landing AI ADE API.
Handles HTTP communication with retry logic.
"""

import json
from typing import Dict, Any
import requests

from ..config import settings
from ..infrastructure.logging import get_logger
from ..infrastructure.retry import ResilientAPIClient, create_retry_config_for_provider
from ..infrastructure.security import cleanup_temp_file
from ..infrastructure.telemetry import EXTRACTION_TIME, EXTRACTION_PAGES

logger = get_logger(__name__)


class DocumentExtractor:
    """
    Client for extracting financial data from PDF documents.
    Uses Landing AI ADE API with retry and circuit breaker protection.
    """
    
    def __init__(self):
        self.api_key = settings.landingai_api_key
        self.base_url = settings.landing_ai_base_url
        
        # Set up resilient client
        self.client = ResilientAPIClient(
            provider="landing_ai",
            model="ade-parser",
            retry_config=create_retry_config_for_provider("landing_ai"),
        )
    
    def extract(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract data from PDF using Landing AI ADE API.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Raw JSON response from Landing AI
            
        Raises:
            Exception: If extraction fails after retries
        """
        logger.info("extraction_started", file_path=pdf_path)
        
        def _do_extraction():
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            with open(pdf_path, 'rb') as f:
                files = {'document': f}
                response = requests.post(
                    f"{self.base_url}/parse",
                    headers=headers,
                    files=files,
                    timeout=settings.landing_ai_timeout
                )
            
            # Only accept 200 OK
            if response.status_code != 200:
                error_msg = f"Landing AI API error: {response.status_code}"
                if response.status_code == 206:
                    error_msg += " - PDF processing incomplete/corrupted"
                else:
                    error_msg += f" - {response.text[:500]}"
                raise Exception(error_msg)
            
            return response.json()
        
        try:
            raw_data = self.client.execute_with_resilience(_do_extraction)
            
            # Log extraction metrics
            metadata = raw_data.get('metadata', {})
            EXTRACTION_PAGES.observe(metadata.get('page_count', 0))
            
            logger.info(
                "extraction_completed",
                page_count=metadata.get('page_count', 0),
                duration_ms=metadata.get('duration_ms', 0),
                credit_usage=metadata.get('credit_usage', 0)
            )
            
            # Save debug output if in debug mode
            if settings.debug:
                debug_path = f"/tmp/landing_ai_debug_{metadata.get('job_id', 'unknown')}.json"
                with open(debug_path, 'w') as f:
                    json.dump(raw_data, f, indent=2)
                logger.debug("debug_output_saved", path=debug_path)
            
            return raw_data
            
        except Exception as e:
            logger.error("extraction_failed", error=str(e))
            raise
