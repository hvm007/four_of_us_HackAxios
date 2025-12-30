"""
Patient Risk Classification ML model client.
Integrates the actual trained model from ML_models/Patient_risk_classification.
"""

import logging
import time
import os
import sys
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import joblib
import pandas as pd

# Add the ML_models directory to the path
ml_models_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'ML_models', 'Patient_risk_classification')
sys.path.append(ml_models_path)

try:
    from inference import predict_patient_risk, calculate_risk_score
except ImportError:
    # Fallback if inference module is not available
    predict_patient_risk = None
    calculate_risk_score = None

from src.utils.error_handling import (
    handle_service_error,
    error_context,
    monitor_external_service,
    log_performance_warning,
    ErrorCategory,
    ErrorSeverity,
    global_error_handler
)

logger = logging.getLogger(__name__)


class PatientRiskMLError(Exception):
    """Base exception for Patient Risk ML model errors."""
    pass


class ModelLoadError(PatientRiskMLError):
    """Raised when model files cannot be loaded."""
    pass


class ModelPredictionError(PatientRiskMLError):
    """Raised when model prediction fails."""
    pass


class PatientRiskMLClient:
    """Client for the actual Patient Risk Classification ML model."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the Patient Risk ML client.
        
        Args:
            model_path: Path to the ML model directory (defaults to ML_models/Patient_risk_classification)
        """
        if model_path is None:
            # Default path relative to backend directory
            model_path = os.path.join(
                os.path.dirname(__file__), 
                '..', '..', '..', 
                'ML_models', 
                'Patient_risk_classification'
            )
        
        self.model_path = os.path.abspath(model_path)
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.model_version = "v1.0.0"
        
        # Load model components
        self._load_model_components()
        
        logger.info(f"PatientRiskMLClient initialized with model path: {self.model_path}")
    
    def _load_model_components(self):
        """Load the trained model, scaler, and feature names."""
        try:
            # Load model
            model_file = os.path.join(self.model_path, 'model.joblib')
            if not os.path.exists(model_file):
                raise ModelLoadError(f"Model file not found: {model_file}")
            
            self.model = joblib.load(model_file)
            logger.info("Loaded trained model")
            
            # Load scaler
            scaler_file = os.path.join(self.model_path, 'scaler.joblib')
            if not os.path.exists(scaler_file):
                raise ModelLoadError(f"Scaler file not found: {scaler_file}")
            
            self.scaler = joblib.load(scaler_file)
            logger.info("Loaded scaler")
            
            # Load feature names
            features_file = os.path.join(self.model_path, 'features.joblib')
            if not os.path.exists(features_file):
                raise ModelLoadError(f"Features file not found: {features_file}")
            
            self.feature_names = joblib.load(features_file)
            logger.info(f"Loaded feature names: {len(self.feature_names)} features")
            
        except Exception as e:
            logger.error(f"Failed to load model components: {e}")
            raise ModelLoadError(f"Failed to load model components: {e}") from e
    
    @monitor_external_service("patient_risk_ml_model", timeout_seconds=5.0, retry_attempts=1)
    def predict_risk(self, heart_rate: float, systolic_bp: float, diastolic_bp: float,
                    respiratory_rate: float, oxygen_saturation: float, temperature: float,
                    arrival_mode: str, acuity_level: int) -> Tuple[float, str, int]:
        """
        Get risk prediction from the Patient Risk Classification model.
        
        Args:
            heart_rate: Heart rate in bpm
            systolic_bp: Systolic blood pressure in mmHg
            diastolic_bp: Diastolic blood pressure in mmHg
            respiratory_rate: Respiratory rate in breaths/min
            oxygen_saturation: Oxygen saturation percentage
            temperature: Body temperature in Celsius
            arrival_mode: Patient arrival mode ("Ambulance" or "Walk-in")
            acuity_level: Clinical severity rating (1-5)
            
        Returns:
            Tuple of (risk_score, risk_category, processing_time_ms)
            risk_score: Float between 0-100
            risk_category: String ("LOW", "MODERATE", "HIGH")
            processing_time_ms: Processing time in milliseconds
            
        Raises:
            ModelPredictionError: If prediction fails
            PatientRiskMLError: For other model errors
        """
        start_time = time.time()
        
        with error_context(
            "patient_risk_ml_prediction",
            ErrorCategory.EXTERNAL_SERVICE,
            context={
                "model_version": self.model_version,
                "model_path": self.model_path
            }
        ):
            try:
                # Prepare patient data in the format expected by the model
                patient_data = {
                    'heartrate': heart_rate,
                    'sbp': systolic_bp,
                    'dbp': diastolic_bp,
                    'resprate': respiratory_rate,
                    'o2sat': oxygen_saturation,
                    'temperature': temperature,
                    'acuity': acuity_level,
                    'arrival_ambulance': 1 if arrival_mode == "Ambulance" else 0
                }
                
                logger.debug(f"Predicting risk for patient data: {patient_data}")
                
                # Use the inference function if available
                if predict_patient_risk is not None:
                    result = predict_patient_risk(
                        patient_data, 
                        self.model, 
                        self.scaler, 
                        self.feature_names
                    )
                    
                    risk_score = result['risk_score']
                    risk_category = result['final_triage_category']
                    
                else:
                    # Fallback to direct model prediction
                    risk_score, risk_category = self._direct_predict(patient_data)
                
                # Calculate processing time
                processing_time_ms = int((time.time() - start_time) * 1000)
                
                # Validate results
                if not isinstance(risk_score, (int, float)) or not (0 <= risk_score <= 100):
                    raise ModelPredictionError(f"Invalid risk score: {risk_score}")
                
                if risk_category not in ["LOW", "MODERATE", "HIGH"]:
                    raise ModelPredictionError(f"Invalid risk category: {risk_category}")
                
                logger.debug(f"Risk prediction completed: score={risk_score}, "
                           f"category={risk_category}, time={processing_time_ms}ms")
                
                return risk_score, risk_category, processing_time_ms
                
            except Exception as e:
                processing_time_ms = int((time.time() - start_time) * 1000)
                logger.error(f"Risk prediction failed after {processing_time_ms}ms: {e}")
                raise ModelPredictionError(f"Risk prediction failed: {e}") from e
    
    def _direct_predict(self, patient_data: Dict[str, Any]) -> Tuple[float, str]:
        """
        Direct prediction using the loaded model components.
        
        Args:
            patient_data: Patient data dictionary
            
        Returns:
            Tuple of (risk_score, risk_category)
        """
        try:
            # Calculate abnormal vitals count (from inference.py logic)
            abnormal = 0
            abnormal += int(patient_data['heartrate'] < 50 or patient_data['heartrate'] > 110)
            abnormal += int(patient_data['sbp'] < 90 or patient_data['sbp'] > 160)
            abnormal += int(patient_data['resprate'] < 12 or patient_data['resprate'] > 20)
            abnormal += int(patient_data['o2sat'] < 95)
            abnormal += int(patient_data['temperature'] < 36.0 or patient_data['temperature'] > 38.0)
            
            patient_data['abnormal_vitals_count'] = abnormal
            
            # Create DataFrame with the required features
            df = pd.DataFrame([patient_data])[self.feature_names]
            
            # Scale the features
            scaled_features = self.scaler.transform(df)
            
            # Get prediction probability
            probability = self.model.predict_proba(scaled_features)[0][1]
            
            # Calculate risk score using the same logic as inference.py
            if calculate_risk_score is not None:
                result = calculate_risk_score(probability, patient_data)
                risk_score = result['risk_score']
                risk_category = result['final_triage_category']
            else:
                # Simplified fallback calculation
                risk_score = probability * 100
                
                # Apply clinical adjustments (simplified)
                clinical_adjustment = 0
                if patient_data['o2sat'] < 88:
                    clinical_adjustment += 20
                elif patient_data['o2sat'] < 92:
                    clinical_adjustment += 10
                
                if patient_data['sbp'] < 90:
                    clinical_adjustment += 15
                
                if patient_data['resprate'] > 24:
                    clinical_adjustment += 10
                
                if patient_data['heartrate'] > 120 or patient_data['heartrate'] < 40:
                    clinical_adjustment += 10
                
                if patient_data['acuity'] >= 4:
                    clinical_adjustment += 15
                elif patient_data['acuity'] >= 3:
                    clinical_adjustment += 10
                
                if patient_data['arrival_ambulance'] == 1:
                    clinical_adjustment += 5
                
                final_score = min(risk_score + clinical_adjustment, 100)
                
                # Determine category
                if final_score < 45:
                    risk_category = 'LOW'
                elif final_score < 65:
                    risk_category = 'MODERATE'
                else:
                    risk_category = 'HIGH'
                
                risk_score = final_score
            
            return risk_score, risk_category
            
        except Exception as e:
            raise ModelPredictionError(f"Direct prediction failed: {e}") from e
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check if the ML model is healthy and responsive.
        
        Returns:
            Dictionary with health status information
        """
        try:
            # Test prediction with normal values
            start_time = time.time()
            risk_score, risk_category, _ = self.predict_risk(
                heart_rate=72.0,
                systolic_bp=120.0,
                diastolic_bp=80.0,
                respiratory_rate=16.0,
                oxygen_saturation=98.0,
                temperature=36.5,
                arrival_mode="Walk-in",
                acuity_level=2
            )
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "mode": "real",
                "model_version": self.model_version,
                "model_path": self.model_path,
                "response_time_ms": response_time_ms,
                "test_prediction": {
                    "risk_score": risk_score,
                    "risk_category": risk_category
                },
                "features_count": len(self.feature_names) if self.feature_names else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "mode": "real",
                "model_version": self.model_version,
                "model_path": self.model_path,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model.
        
        Returns:
            Dictionary with model information
        """
        return {
            "model_version": self.model_version,
            "model_path": self.model_path,
            "model_loaded": self.model is not None,
            "scaler_loaded": self.scaler is not None,
            "features_loaded": self.feature_names is not None,
            "feature_count": len(self.feature_names) if self.feature_names else 0,
            "feature_names": list(self.feature_names) if self.feature_names else []
        }