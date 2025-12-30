"""
FastAPI main application for Patient Risk Classifier Backend.
Configures the API with middleware, error handlers, and routing.
"""

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Callable, Dict

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from src.models.api_models import ErrorResponse
from src.utils.database import close_database, init_database
from src.utils.validation import (
    sanitize_string, 
    validate_patient_id, 
    sanitize_dict, 
    DANGEROUS_PATTERNS,
    create_safe_error_details
)

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("patient_risk_classifier")


def create_secure_error_response(
    error_code: str,
    user_message: str,
    request_id: str = None,
    details: Dict[str, Any] = None,
    log_details: str = None
) -> ErrorResponse:
    """
    Create a secure error response that doesn't expose sensitive information.
    
    Implements Requirement 6.5: User-friendly error messages without exposing 
    sensitive system information.
    
    Args:
        error_code: Error type/code for categorization
        user_message: User-friendly error message
        request_id: Optional request ID for support reference
        details: Optional safe details to include in response
        log_details: Optional detailed information for logging only (not in response)
        
    Returns:
        ErrorResponse with sanitized content
    """
    # Log detailed error information for debugging (internal only)
    if log_details:
        logger.error(f"Error details for {error_code}: {log_details}")
    
    safe_details = {}
    if request_id:
        safe_details["request_id"] = request_id
    
    if details:
        safe_details.update(create_safe_error_details(details))
    
    # Ensure error message is also sanitized
    sanitized_message = sanitize_string(user_message) if isinstance(user_message, str) else user_message
    
    return ErrorResponse(
        error=error_code,
        message=sanitized_message,
        details=safe_details if safe_details else None
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests and responses with timing information."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID for tracing
        request_id = str(uuid.uuid4())[:8]
        
        # Store request ID in state for access in handlers
        request.state.request_id = request_id
        
        # Log incoming request
        start_time = time.time()
        logger.info(
            f"[{request_id}] Request: {request.method} {request.url.path} "
            f"- Client: {request.client.host if request.client else 'unknown'}"
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            logger.info(
                f"[{request_id}] Response: {response.status_code} "
                f"- Duration: {process_time:.3f}s"
            )
            
            # Add request ID to response headers for client-side tracing
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"[{request_id}] Error during request processing: {type(e).__name__}: {str(e)} "
                f"- Duration: {process_time:.3f}s"
            )
            raise


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware for sanitizing input data to prevent injection attacks."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = getattr(request.state, "request_id", "unknown")
        
        # Sanitize query parameters
        # Note: Query params are read-only, so we log warnings for suspicious content
        suspicious_params = []
        for key, value in request.query_params.items():
            try:
                sanitized = sanitize_string(value)
                if sanitized != value:
                    suspicious_params.append(key)
            except ValueError as e:
                logger.warning(
                    f"[{request_id}] Malicious content detected in query param '{key}': {e}"
                )
                return JSONResponse(
                    status_code=400,
                    content=create_secure_error_response(
                        error_code="INVALID_INPUT",
                        user_message="Invalid characters detected in request parameters",
                        request_id=request_id
                    ).model_dump(mode='json')
                )
        
        if suspicious_params:
            logger.warning(
                f"[{request_id}] Potentially malicious content detected in query params: {suspicious_params}"
            )
        
        # Sanitize path parameters (check for suspicious patterns)
        path = request.url.path
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                logger.warning(
                    f"[{request_id}] Potentially malicious content detected in path: {path}"
                )
                return JSONResponse(
                    status_code=400,
                    content=create_secure_error_response(
                        error_code="INVALID_REQUEST",
                        user_message="Invalid request path detected",
                        request_id=request_id,
                        log_details=f"Suspicious path: {path}"
                    ).model_dump(mode='json')
                )
        
        # Check for path traversal attempts
        if "../" in path or "..\\" in path:
            logger.warning(f"[{request_id}] Path traversal attempt detected: {path}")
            return JSONResponse(
                status_code=400,
                content=create_secure_error_response(
                    error_code="INVALID_REQUEST",
                    user_message="Invalid request path",
                    request_id=request_id
                ).model_dump(mode='json')
            )
        
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers to responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers (Requirement 6.4: Security measures)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        # Remove server information (use del instead of pop for MutableHeaders)
        if "Server" in response.headers:
            del response.headers["Server"]
        
        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware for basic protection."""
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # In production, use Redis or similar
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        request_id = getattr(request.state, "request_id", "unknown")
        current_time = time.time()
        
        # Clean old entries
        cutoff_time = current_time - self.window_seconds
        self.requests = {
            ip: timestamps for ip, timestamps in self.requests.items()
            if any(t > cutoff_time for t in timestamps)
        }
        
        # Update current IP's requests
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        # Remove old timestamps for this IP
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if t > cutoff_time
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= self.max_requests:
            logger.warning(f"[{request_id}] Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content=create_secure_error_response(
                    error_code="RATE_LIMIT_EXCEEDED",
                    user_message="Too many requests. Please try again later.",
                    request_id=request_id,
                    details={"retry_after": self.window_seconds}
                ).model_dump(mode='json')
            )
        
        # Add current request
        self.requests[client_ip].append(current_time)
        
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("🏥 Patient Risk Classifier Backend starting up...")
    logger.info("📊 Initializing database connections...")
    init_database()
    logger.info("✅ Application startup complete")

    yield

    # Shutdown
    logger.info("🏥 Patient Risk Classifier Backend shutting down...")
    logger.info("📊 Closing database connections...")
    close_database()
    logger.info("✅ Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="Patient Risk Classifier Backend",
    description="""
    A RESTful API system for patient risk classification that continuously monitors 
    patient vital signs and uses a pre-trained machine learning model to assess 
    deterioration risk.
    
    ## Features
    
    * **Patient Registration** - Register patients with initial vital signs and clinical information
    * **Vital Signs Monitoring** - Update and track patient vital signs over time
    * **Risk Assessment** - Automated risk scoring using machine learning models
    * **Historical Data** - Access to complete patient history and trends
    * **High-Risk Alerts** - Query and identify high-risk patients
    
    ## Medical Validation
    
    All vital signs are validated against medically acceptable ranges:
    - Heart Rate: 30-200 bpm
    - Systolic BP: 50-300 mmHg  
    - Diastolic BP: 20-200 mmHg
    - Respiratory Rate: 5-60 breaths/min
    - Oxygen Saturation: 50-100%
    - Temperature: 30-45°C
    """,
    version="1.0.0",
    contact={
        "name": "Patient Risk Classifier Team",
        "email": "support@patientrisk.example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add input sanitization middleware
app.add_middleware(InputSanitizationMiddleware)

# Add rate limiting middleware (basic protection)
app.add_middleware(RateLimitingMiddleware, max_requests=100, window_seconds=60)


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent error response format."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log the HTTP exception with appropriate level
    if exc.status_code >= 500:
        logger.error(
            f"[{request_id}] HTTP {exc.status_code}: {exc.detail} "
            f"- Path: {request.url.path}"
        )
    else:
        logger.warning(
            f"[{request_id}] HTTP {exc.status_code}: {exc.detail} "
            f"- Path: {request.url.path}"
        )
    
    # Create secure error response based on status code
    if exc.status_code == 404:
        error_response = create_secure_error_response(
            error_code="RESOURCE_NOT_FOUND",
            user_message="The requested resource was not found",
            request_id=request_id,
            log_details=f"Original detail: {exc.detail}"
        )
    elif exc.status_code == 400:
        error_response = create_secure_error_response(
            error_code="BAD_REQUEST",
            user_message="Invalid request data provided",
            request_id=request_id,
            details=getattr(exc, "details", None),
            log_details=f"Original detail: {exc.detail}"
        )
    elif exc.status_code == 422:
        error_response = create_secure_error_response(
            error_code="VALIDATION_ERROR",
            user_message="Request data validation failed",
            request_id=request_id,
            details=getattr(exc, "details", None),
            log_details=f"Original detail: {exc.detail}"
        )
    elif exc.status_code == 429:
        error_response = create_secure_error_response(
            error_code="RATE_LIMIT_EXCEEDED",
            user_message="Too many requests. Please try again later.",
            request_id=request_id,
            details={"retry_after": 60}
        )
    elif exc.status_code >= 500:
        error_response = create_secure_error_response(
            error_code="INTERNAL_SERVER_ERROR",
            user_message="An internal server error occurred. Please try again later.",
            request_id=request_id,
            log_details=f"Original detail: {exc.detail}"
        )
    else:
        # Generic error response for other status codes
        error_response = create_secure_error_response(
            error_code=f"HTTP_{exc.status_code}",
            user_message="An error occurred while processing your request",
            request_id=request_id,
            log_details=f"Original detail: {exc.detail}"
        )
    
    return JSONResponse(
        status_code=exc.status_code, 
        content=error_response.model_dump(mode='json')
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with secure error responses."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log the full exception details for debugging (internal only)
    logger.error(
        f"[{request_id}] Unexpected error: {type(exc).__name__}: {str(exc)} "
        f"- Path: {request.url.path}",
        exc_info=True  # Include stack trace in logs
    )

    # Return generic error response without exposing internal details
    # This satisfies Requirement 6.5: user-friendly messages without sensitive info
    error_response = create_secure_error_response(
        error_code="INTERNAL_SERVER_ERROR",
        user_message="An unexpected error occurred. Please try again later.",
        request_id=request_id
    )
    return JSONResponse(status_code=500, content=error_response.model_dump(mode='json'))


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors with descriptive messages."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Extract validation error details
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        # Sanitize error messages to prevent information leakage
        safe_message = sanitize_string(error["msg"])
        errors.append({
            "field": field,
            "message": safe_message,
            "type": error["type"]
        })
    
    logger.warning(
        f"[{request_id}] Validation error: {len(errors)} field(s) invalid "
        f"- Path: {request.url.path}"
    )
    
    error_response = create_secure_error_response(
        error_code="VALIDATION_ERROR",
        user_message="Invalid input data. Please check the provided values.",
        request_id=request_id,
        details={"validation_errors": errors},
        log_details=f"Full validation errors: {exc.errors()}"
    )
    return JSONResponse(status_code=422, content=error_response.model_dump(mode='json'))


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint for system monitoring.

    Returns system status and basic information.
    """
    return {
        "status": "healthy",
        "service": "Patient Risk Classifier Backend",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",  # TODO: Add actual database health check in task 3.1
        "ml_model": "available",  # TODO: Add actual ML model health check in task 5.5
    }


# Demo endpoints for development
@app.get("/demo/info", tags=["Demo"])
async def demo_info() -> Dict[str, Any]:
    """
    Demo information endpoint.

    Provides information about the demo system and sample data.
    """
    return {
        "message": "Patient Risk Classifier Backend Demo",
        "description": "Real-time patient deterioration risk assessment system",
        "endpoints": {"health": "/health", "docs": "/docs", "openapi": "/openapi.json"},
        "sample_data": {
            "patients": "Sample patients will be available after database setup",
            "vital_signs": "Sample vital signs data for testing",
            "risk_assessments": "Sample risk assessment results",
        },
        "next_steps": [
            "Complete database setup (Task 3.1)",
            "Implement patient registration (Task 6.2)",
            "Add vital signs endpoints (Task 6.4)",
            "Integrate ML risk model (Task 5.5)",
        ],
    }


# Custom OpenAPI schema
def custom_openapi():
    """Generate custom OpenAPI schema with additional metadata."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add custom schema extensions
    openapi_schema["info"]["x-logo"] = {"url": "https://example.com/logo.png"}

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Include routers for API endpoints
from src.api.patients import router as patients_router
from src.api.vitals import router as vitals_router

app.include_router(patients_router)
app.include_router(vitals_router)
