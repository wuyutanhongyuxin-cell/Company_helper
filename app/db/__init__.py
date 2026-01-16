"""
Database module - 数据库模块
Provides ORM models, repositories, and session management.
"""

from .session import (
    init_database_simple,
    create_all_tables,
    session_scope,
    get_engine,
)
from .models import (
    Base,
    User,
    UserRole,
    Employee,
    EmployeeStatus,
    SalaryStructure,
    Attendance,
    Adjustment,
    AdjustmentType,
    PayrollRun,
    PayrollStatus,
    PayrollSlip,
    AuditLog,
)
from .repositories import (
    UserRepository,
    EmployeeRepository,
    SalaryStructureRepository,
    AttendanceRepository,
    AdjustmentRepository,
    PayrollRunRepository,
    PayrollSlipRepository,
    AuditLogRepository,
)

__all__ = [
    # Session
    "init_database_simple",
    "create_all_tables",
    "session_scope",
    "get_engine",
    # Models
    "Base",
    "User",
    "UserRole",
    "Employee",
    "EmployeeStatus",
    "SalaryStructure",
    "Attendance",
    "Adjustment",
    "AdjustmentType",
    "PayrollRun",
    "PayrollStatus",
    "PayrollSlip",
    "AuditLog",
    # Repositories
    "UserRepository",
    "EmployeeRepository",
    "SalaryStructureRepository",
    "AttendanceRepository",
    "AdjustmentRepository",
    "PayrollRunRepository",
    "PayrollSlipRepository",
    "AuditLogRepository",
]
