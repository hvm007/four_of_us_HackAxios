#!/usr/bin/env python3
"""
Complete integration test for Patient Risk Classification system.
Tests the full flow from API endpoints to ML model predictions.
"""

import sys
import os
import json
import requests
import time
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_api_integration():
    """Test the complete API integration with ML model."""
    base_url = "http://localhost:8000"
    
    # Test data
    test_patient = {
        "patient_id": "TEST_API_PATIENT",
        "arrival_mode": "Ambulance",
        "acuity_level": 3,
        "initial_vitals": {
            "heart_rate": 95.0,
            "systolic_bp": 150.0,
            "diastolic_bp": 95.0,
            "respiratory_rate": 22.0,
            "oxygen_saturation": 94.0,
            "temperature": 38.5,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }
    
    updated_vitals = {
        "heart_rate": 110.0,
        "systolic_bp": 160.0,
        "diastolic_bp": 100.0,
        "respiratory_rate": 26.0,
        "oxygen_saturation": 92.0,
        "temperature": 39.0
    }
    
    try:
        # Test 1: Health check
        logger.info("Testing health check endpoint...")
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health_data = response.json()
            logger.info(f"✅ Health check passed: {health_data['status']}")
        else:
            logger.error(f"❌ Health check failed: {response.status_code}")
            return False
        
        # Test 2: Patient registration with ML risk assessment
        logger.info("Testing patient registration with ML risk assessment...")
        response = requests.post(
            f"{base_url}/patients",
            json=test_patient,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            patient_data = response.json()
            logger.info("✅ Patient registration successful")
            logger.info(f"  Patient ID: {patient_data['patient_id']}")
            logger.info(f"  Risk Score: {patient_data['current_risk']['risk_score']}")
            logger.info(f"  Risk Category: {patient_data['current_risk']['risk_category']}")
            logger.info(f"  Risk Flag: {patient_data['current_risk']['risk_flag']}")
            logger.info(f"  Model Version: {patient_data['current_risk']['model_version']}")
        else:
            logger.error(f"❌ Patient registration failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        
        # Test 3: Vital signs update with ML risk assessment
        logger.info("Testing vital signs update with ML risk assessment...")
        response = requests.put(
            f"{base_url}/patients/{test_patient['patient_id']}/vitals",
            json=updated_vitals,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            update_data = response.json()
            logger.info("✅ Vital signs update successful")
            logger.info(f"  Message: {update_data['message']}")
        else:
            logger.error(f"❌ Vital signs update failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        
        # Test 4: Get updated patient status
        logger.info("Testing patient status retrieval...")
        response = requests.get(f"{base_url}/patients/{test_patient['patient_id']}")
        
        if response.status_code == 200:
            status_data = response.json()
            logger.info("✅ Patient status retrieval successful")
            logger.info(f"  Updated Risk Score: {status_data['current_risk']['risk_score']}")
            logger.info(f"  Updated Risk Category: {status_data['current_risk']['risk_category']}")
            logger.info(f"  Updated Risk Flag: {status_data['current_risk']['risk_flag']}")
            logger.info(f"  Heart Rate: {status_data['current_vitals']['heart_rate']}")
            logger.info(f"  Oxygen Saturation: {status_data['current_vitals']['oxygen_saturation']}")
        else:
            logger.error(f"❌ Patient status retrieval failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        
        # Test 5: Get patient history
        logger.info("Testing patient history retrieval...")
        response = requests.get(f"{base_url}/patients/{test_patient['patient_id']}/history")
        
        if response.status_code == 200:
            history_data = response.json()
            logger.info("✅ Patient history retrieval successful")
            logger.info(f"  Total data points: {history_data['total_count']}")
            if history_data['data_points']:
                latest_point = history_data['data_points'][-1]
                logger.info(f"  Latest risk score: {latest_point['risk_assessment']['risk_score']}")
                logger.info(f"  Latest risk category: {latest_point['risk_assessment']['risk_category']}")
        else:
            logger.error(f"❌ Patient history retrieval failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        
        # Test 6: Get high-risk patients
        logger.info("Testing high-risk patients query...")
        response = requests.get(f"{base_url}/patients/high-risk")
        
        if response.status_code == 200:
            high_risk_data = response.json()
            logger.info("✅ High-risk patients query successful")
            logger.info(f"  Total high-risk patients: {high_risk_data['total_count']}")
        else:
            logger.error(f"❌ High-risk patients query failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
        
        logger.info("🎉 All API integration tests passed!")
        return True
        
    except requests.exceptions.ConnectionError:
        logger.error("❌ Could not connect to API server. Make sure it's running on http://localhost:8000")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during API testing: {e}")
        return False


def main():
    """Run the complete integration test."""
    logger.info("Starting Complete Integration Test...")
    logger.info("This test requires the API server to be running on http://localhost:8000")
    
    # Wait a moment for user to start server if needed
    logger.info("Starting test in 3 seconds... (Press Ctrl+C to cancel)")
    try:
        time.sleep(3)
    except KeyboardInterrupt:
        logger.info("Test cancelled by user")
        return 1
    
    success = test_api_integration()
    
    if success:
        logger.info("\n" + "="*60)
        logger.info("🎉 COMPLETE INTEGRATION TEST PASSED!")
        logger.info("✅ Patient Risk Classification ML model is fully integrated")
        logger.info("✅ API endpoints are working correctly")
        logger.info("✅ Risk assessments are being generated automatically")
        logger.info("="*60)
        return 0
    else:
        logger.error("\n" + "="*60)
        logger.error("❌ INTEGRATION TEST FAILED!")
        logger.error("Check the logs above for specific error details")
        logger.error("="*60)
        return 1


if __name__ == "__main__":
    exit(main())