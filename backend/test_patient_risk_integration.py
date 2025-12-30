#!/usr/bin/env python3
"""
Test script to verify Patient Risk ML model integration.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from src.utils.patient_risk_ml_client import PatientRiskMLClient
from src.services.risk_assessment_service import RiskAssessmentService
from src.utils.database import get_db_session
from src.models.db_models import Patient, VitalSigns, ArrivalModeEnum
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ml_client():
    """Test the Patient Risk ML client directly."""
    logger.info("Testing Patient Risk ML Client...")
    
    try:
        # Initialize the client
        client = PatientRiskMLClient()
        
        # Test health check
        health = client.health_check()
        logger.info(f"Health check: {health}")
        
        # Test prediction with sample data
        risk_score, risk_category, processing_time = client.predict_risk(
            heart_rate=85.0,
            systolic_bp=140.0,
            diastolic_bp=90.0,
            respiratory_rate=18.0,
            oxygen_saturation=96.0,
            temperature=37.2,
            arrival_mode="Ambulance",
            acuity_level=3
        )
        
        logger.info(f"Prediction result:")
        logger.info(f"  Risk Score: {risk_score}")
        logger.info(f"  Risk Category: {risk_category}")
        logger.info(f"  Processing Time: {processing_time}ms")
        
        return True
        
    except Exception as e:
        logger.error(f"ML Client test failed: {e}")
        return False


def test_service_integration():
    """Test the risk assessment service with ML integration."""
    logger.info("Testing Risk Assessment Service integration...")
    
    try:
        with get_db_session() as db:
            # Initialize service
            service = RiskAssessmentService(db)
            
            # Create a test patient
            patient = Patient(
                patient_id="TEST_PATIENT_ML",
                arrival_mode=ArrivalModeEnum.AMBULANCE,
                acuity_level=3,
                registration_time=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )
            db.add(patient)
            db.flush()
            
            # Create test vital signs
            vital_signs = VitalSigns(
                patient_id=patient.patient_id,
                heart_rate=85.0,
                systolic_bp=140.0,
                diastolic_bp=90.0,
                respiratory_rate=18.0,
                oxygen_saturation=96.0,
                temperature=37.2,
                timestamp=datetime.utcnow(),
                recorded_by="Test System"
            )
            db.add(vital_signs)
            db.flush()
            
            # Perform risk assessment
            risk_assessment = service.assess_risk_for_vital_signs(vital_signs)
            
            logger.info(f"Risk Assessment result:")
            logger.info(f"  Patient ID: {risk_assessment.patient_id}")
            logger.info(f"  Risk Score: {risk_assessment.risk_score}")
            logger.info(f"  Risk Category: {risk_assessment.risk_category}")
            logger.info(f"  Risk Flag: {risk_assessment.risk_flag}")
            logger.info(f"  Model Version: {risk_assessment.model_version}")
            logger.info(f"  Processing Time: {risk_assessment.processing_time_ms}ms")
            
            # Clean up test data
            db.delete(risk_assessment)
            db.delete(vital_signs)
            db.delete(patient)
            db.commit()
            
            return True
            
    except Exception as e:
        logger.error(f"Service integration test failed: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("Starting Patient Risk ML Integration Tests...")
    
    # Test 1: ML Client
    ml_client_success = test_ml_client()
    
    # Test 2: Service Integration
    service_success = test_service_integration()
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY:")
    logger.info(f"  ML Client Test: {'PASS' if ml_client_success else 'FAIL'}")
    logger.info(f"  Service Integration Test: {'PASS' if service_success else 'FAIL'}")
    
    if ml_client_success and service_success:
        logger.info("🎉 All tests passed! Patient Risk ML integration is working.")
        return 0
    else:
        logger.error("❌ Some tests failed. Check the logs above.")
        return 1


if __name__ == "__main__":
    exit(main())