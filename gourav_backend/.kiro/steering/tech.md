---
inclusion: always
---

# Technology Stack & Development Guidelines

## Core Technologies & Implementation Rules

### Backend Framework
- **Python 3.8+**: ALWAYS use type hints for function signatures and class attributes
- **FastAPI**: Use dependency injection for database sessions and services
- **Pydantic**: Create separate models for requests/responses in `src/models/api_models.py`
- **SQLAlchemy**: Use async sessions, define models in `src/models/db_models.py`

### Database & Storage
- **SQLite**: Development database file is `patient_risk_test.db` in project root
- **Time-series data**: VitalSigns table MUST include timestamp with timezone
- **Relationships**: Patient (1:many) → VitalSigns, Patient (1:many) → RiskAssessments
- **Indexes**: ALWAYS create indexes on patient_id and timestamp fields

### Machine Learning Integration
- **Mock implementation**: Use `MLClient` class from `src/utils/ml_client.py`
- **Risk scores**: MUST return float between 0.0-1.0 (0=low risk, 1=high risk)
- **Trigger pattern**: Risk assessment MUST run automatically on vital signs updates
- **Service isolation**: ML calls ONLY through `RiskAssessmentService`

### Testing Requirements
- **Property-based tests**: Use Hypothesis with minimum 100 iterations per test
- **Test organization**: Mirror `src/` structure in `tests/` directory
- **Coverage target**: 90% minimum for all files in `src/services/`
- **Test naming**: `test_<functionality>_<scenario>.py` format

## Mandatory Code Patterns

### Architecture Layers (STRICT)
```
API Layer (src/api/) → Service Layer (src/services/) → Repository Layer (src/repositories/) → Database
```
- API controllers ONLY call services, never repositories directly
- Services contain ALL business logic and validation
- Repositories handle ONLY database operations
- NO circular dependencies between layers

### Error Handling (REQUIRED)
- Use custom exceptions: `ValidationError`, `BusinessLogicError`, `DatabaseError`
- ALWAYS include descriptive error messages with context
- API layer MUST catch service exceptions and return appropriate HTTP status codes
- NEVER expose internal error details to API responses

### Medical Data Validation
- Vital signs MUST be within physiologically reasonable ranges:
  - Heart rate: 30-200 bpm
  - Blood pressure: systolic 70-250, diastolic 40-150 mmHg
  - Temperature: 32-45°C
  - Oxygen saturation: 70-100%
- Patient IDs MUST be unique and non-empty
- Timestamps MUST be in ISO 8601 format with timezone

## File Organization & Naming

### Directory Structure (ENFORCE)
```
src/
├── api/           # FastAPI route handlers only
├── services/      # Business logic and validation
├── repositories/  # Database operations only  
├── models/        # Pydantic and SQLAlchemy models
└── utils/         # Shared utilities and ML client
```

### Naming Conventions
- **Files**: snake_case with layer suffix (`patient_service.py`)
- **Classes**: PascalCase (`PatientService`, `VitalSignsRepository`)
- **Functions/variables**: snake_case (`get_patient_by_id`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_HEART_RATE = 200`)

### Import Rules
- Use absolute imports: `from src.services.patient_service import PatientService`
- Layer dependencies: API → Services → Repositories → Models
- NO imports from higher layers (repositories cannot import services)

## API Design Standards (MANDATORY)

### Request/Response Format
- **Content-Type**: `application/json` for all endpoints
- **Field naming**: snake_case in JSON (`patient_id`, `vital_signs`)
- **Datetime format**: ISO 8601 with timezone (`2024-01-15T10:30:00Z`)
- **Error responses**: Include `error_code`, `message`, and `details` fields

### HTTP Status Codes (STRICT)
- **200**: Successful retrieval or update
- **201**: Successful creation with resource returned
- **400**: Client error (validation, malformed request)
- **404**: Resource not found
- **422**: Business logic validation failure
- **500**: Internal server error (log details, return generic message)

### Endpoint Patterns
- **GET /patients/{patient_id}**: Retrieve single patient
- **POST /patients**: Create new patient (returns 201)
- **POST /patients/{patient_id}/vitals**: Add vital signs (triggers risk assessment)
- **GET /patients/{patient_id}/vitals**: Retrieve vital signs history
- **GET /patients/{patient_id}/risk**: Get current risk assessment

## Development Commands

### Testing (REQUIRED BEFORE COMMITS)
```bash
# Run all tests with coverage
pytest --cov=src --cov-report=term-missing

# Property-based tests only
pytest tests/property/ -v

# Specific test file
pytest tests/unit/test_patient_service.py -v
```

### Development Server
```bash
# Start demo server (includes sample data)
python run_demo.py

# API documentation: http://localhost:8000/docs
# Health check: http://localhost:8000/health
```

## Critical Implementation Rules

### Database Operations
- ALWAYS use async database sessions
- NEVER perform database operations in API layer
- Use repository pattern for all database access
- Implement proper transaction handling for multi-table operations

### Risk Assessment Automation
- Risk assessment MUST trigger automatically when vital signs are added/updated
- Use background task or service method call (not separate API endpoint)
- Store risk assessment results with timestamp and model version
- Handle ML service failures gracefully (log error, don't fail vital signs storage)

### Data Integrity
- Validate patient exists before adding vital signs
- Ensure chronological ordering of vital signs data
- Prevent duplicate patient IDs during registration
- Maintain referential integrity between patients, vital signs, and risk assessments

### Security & Privacy
- NEVER log patient personal information
- Use patient IDs (not names) in logs and error messages
- Validate all input data at API and service layers
- Sanitize error messages before returning to clients