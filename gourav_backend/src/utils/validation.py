"""
Input validation utilities for security and data integrity.
Implements Requirements 6.2, 6.4, and 6.5 for secure input handling.
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Security patterns for input sanitization (Requirement 6.4)
DANGEROUS_PATTERNS = [
    r"<script[^>]*>.*?</script>",  # XSS script tags
    r"javascript:",  # JavaScript protocol
    r"on\w+\s*=",  # Event handlers
    r"--",  # SQL comment
    r";.*(?:drop|delete|truncate|alter|create|insert|update)",  # SQL injection
    r"'\s*or\s*'",  # SQL injection OR
    r"'\s*and\s*'",  # SQL injection AND
    r"\$\{.*\}",  # Template injection
    r"\{\{.*\}\}",  # Template injection
    r"union\s+select",  # SQL injection UNION
    r"exec\s*\(",  # Code execution
    r"eval\s*\(",  # Code execution
    r"<iframe",  # XSS iframe
    r"<object",  # XSS object
    r"<embed",  # XSS embed
    r"vbscript:",  # VBScript protocol
    r"data:text/html",  # Data URI XSS
    r"\.\.\/",  # Path traversal
    r"\.\.\\",  # Path traversal (Windows)
    r"\/etc\/passwd",  # File inclusion
    r"\/proc\/",  # System file access
    r"cmd\.exe",  # Command execution
    r"powershell",  # PowerShell execution
    r"<\?php",  # PHP code injection
    r"<%.*%>",  # ASP code injection
]

# Additional security patterns for patient ID validation
PATIENT_ID_DANGEROUS_PATTERNS = [
    r"[<>\"'&]",  # HTML/XML special characters
    r"[\x00-\x1f\x7f-\x9f]",  # Control characters
    r"\\x[0-9a-fA-F]{2}",  # Hex encoded characters
    r"%[0-9a-fA-F]{2}",  # URL encoded characters
]


def sanitize_string(value: str) -> str:
    """
    Sanitize a string value to prevent injection attacks.
    
    Implements Requirement 6.4: Input sanitization to prevent injection attacks.
    
    Args:
        value: The string to sanitize
        
    Returns:
        Sanitized string with dangerous patterns removed
        
    Raises:
        ValueError: If the input contains too many dangerous patterns (potential attack)
    """
    if not isinstance(value, str):
        return value
    
    original_value = value
    sanitized = value
    dangerous_count = 0
    
    # Count and remove dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        matches = re.findall(pattern, sanitized, flags=re.IGNORECASE)
        if matches:
            dangerous_count += len(matches)
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    
    # If too many dangerous patterns detected, likely an attack
    if dangerous_count > 3:
        logger.warning(f"Potential attack detected: {dangerous_count} dangerous patterns in input")
        raise ValueError("Input contains potentially malicious content")
    
    # Remove null bytes and other control characters
    sanitized = sanitized.replace("\x00", "")
    sanitized = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)
    
    # Log if significant sanitization occurred
    if len(sanitized) < len(original_value) * 0.8:
        logger.warning(f"Significant content removed during sanitization: {len(original_value)} -> {len(sanitized)}")
    
    return sanitized.strip()


def validate_patient_id(patient_id: str) -> str:
    """
    Validate and sanitize patient ID according to security requirements.
    
    Implements Requirement 6.2: Clear error messages for invalid patient IDs.
    Implements Requirement 6.4: Input sanitization for patient identifiers.
    
    Args:
        patient_id: Patient identifier to validate
        
    Returns:
        Sanitized patient ID
        
    Raises:
        ValueError: If patient ID is invalid or contains dangerous patterns
    """
    if not patient_id or not isinstance(patient_id, str):
        raise ValueError("Patient ID must be a non-empty string")
    
    # Check for dangerous patterns specific to patient IDs
    for pattern in PATIENT_ID_DANGEROUS_PATTERNS:
        if re.search(pattern, patient_id):
            raise ValueError("Patient ID contains invalid characters")
    
    # Basic format validation
    if len(patient_id.strip()) == 0:
        raise ValueError("Patient ID cannot be empty or whitespace only")
    
    if len(patient_id) > 50:
        raise ValueError("Patient ID cannot exceed 50 characters")
    
    # Check for suspicious patterns that might indicate injection attempts
    if any(keyword in patient_id.lower() for keyword in ['select', 'drop', 'delete', 'insert', 'update', 'union']):
        raise ValueError("Patient ID contains invalid content")
    
    sanitized_id = sanitize_string(patient_id)
    
    # Ensure sanitization didn't remove too much content
    if len(sanitized_id) < len(patient_id) * 0.9:
        raise ValueError("Patient ID contains too many invalid characters")
    
    return sanitized_id


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized dictionary
    """
    if not isinstance(data, dict):
        return data
    
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(item) if isinstance(item, dict)
                else sanitize_string(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def validate_medical_ranges(vital_signs: Dict[str, float]) -> List[str]:
    """
    Validate vital signs are within medically acceptable ranges.
    
    Implements Requirement 6.1: Validate measurements against medical ranges.
    
    Args:
        vital_signs: Dictionary of vital sign measurements
        
    Returns:
        List of validation error messages (empty if all valid)
    """
    errors = []
    
    # Define medical ranges (extended for critical cases)
    ranges = {
        "heart_rate": (30, 200, "bpm"),
        "systolic_bp": (50, 300, "mmHg"),
        "diastolic_bp": (20, 200, "mmHg"),
        "respiratory_rate": (5, 60, "breaths/min"),
        "oxygen_saturation": (50, 100, "%"),
        "temperature": (30, 45, "°C"),
    }
    
    for field, (min_val, max_val, unit) in ranges.items():
        if field in vital_signs:
            value = vital_signs[field]
            if not isinstance(value, (int, float)):
                errors.append(f"{field} must be a number")
            elif value < min_val or value > max_val:
                errors.append(f"{field} must be between {min_val} and {max_val} {unit}")
    
    # Additional validation: Blood pressure relationship
    if "systolic_bp" in vital_signs and "diastolic_bp" in vital_signs:
        if vital_signs["diastolic_bp"] >= vital_signs["systolic_bp"]:
            errors.append("Diastolic blood pressure must be less than systolic blood pressure")
    
    return errors


def validate_time_range(start_time, end_time) -> List[str]:
    """
    Validate time range parameters.
    
    Args:
        start_time: Start datetime
        end_time: End datetime
        
    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []
    
    if start_time and end_time:
        if start_time >= end_time:
            errors.append("Start time must be before end time")
    
    return errors


def is_suspicious_input(text: str) -> bool:
    """
    Check if input text contains suspicious patterns that might indicate an attack.
    
    Args:
        text: Text to check
        
    Returns:
        True if suspicious patterns detected
    """
    if not isinstance(text, str):
        return False
    
    suspicious_count = 0
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            suspicious_count += 1
    
    return suspicious_count > 0


def create_safe_error_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create safe error details that don't expose sensitive information.
    
    Implements Requirement 6.5: User-friendly error messages without exposing 
    sensitive system information.
    
    Args:
        details: Original error details
        
    Returns:
        Sanitized error details safe for client response
    """
    if not details:
        return {}
    
    # Only include safe, non-sensitive details
    safe_keys = {
        "field", "fields", "validation_errors", "allowed_values", 
        "request_id", "error_count", "retry_after", "supported_formats",
        "min_value", "max_value", "expected_format"
    }
    
    safe_details = {}
    for key, value in details.items():
        if key in safe_keys:
            # Sanitize the detail values as well
            if isinstance(value, str):
                safe_details[key] = sanitize_string(value)
            elif isinstance(value, list):
                safe_details[key] = [
                    sanitize_string(item) if isinstance(item, str) else item 
                    for item in value
                ]
            else:
                safe_details[key] = value
    
    return safe_details