"""
Database Models - 数据库模型
SQLAlchemy ORM models for the payroll management system.
"""

import enum
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    Numeric, Enum, ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# =============================================================================
# Enums
# =============================================================================

class UserRole(enum.Enum):
    """User role enumeration."""
    ADMIN = "admin"          # 管理员 - 全部权限
    FINANCE = "finance"      # 财务 - 工资计算、导出
    HR = "hr"                # 人事 - 员工管理、考勤
    EMPLOYEE = "employee"    # 员工 - 仅查看自己的工资条


class EmployeeStatus(enum.Enum):
    """Employee status enumeration."""
    ACTIVE = "active"        # 在职
    INACTIVE = "inactive"    # 离职
    SUSPENDED = "suspended"  # 停薪留职


class AdjustmentType(enum.Enum):
    """Salary adjustment type enumeration."""
    ADD = "add"              # 增项（奖金、补贴）
    DEDUCT = "deduct"        # 扣项（罚款、预支）


class PayrollStatus(enum.Enum):
    """Payroll run status enumeration."""
    DRAFT = "draft"          # 草稿 - 可修改
    LOCKED = "locked"        # 已锁定 - 不可修改
    PAID = "paid"            # 已发放


# =============================================================================
# Models
# =============================================================================

class User(Base):
    """
    User model - 用户表
    Stores user accounts for system access.
    """
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.EMPLOYEE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Optional: Link to employee record
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id"), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    employee = relationship("Employee", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role={self.role.value})>"


class Employee(Base):
    """
    Employee model - 员工表
    Stores employee information with encrypted sensitive fields.
    """
    __tablename__ = "employees"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_no: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    
    # Encrypted sensitive fields (stored as base64 strings)
    bank_card_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    id_number_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[EmployeeStatus] = mapped_column(Enum(EmployeeStatus), default=EmployeeStatus.ACTIVE)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="employee", uselist=False)
    salary_structure = relationship("SalaryStructure", back_populates="employee", uselist=False)
    attendances = relationship("Attendance", back_populates="employee")
    adjustments = relationship("Adjustment", back_populates="employee")
    payroll_slips = relationship("PayrollSlip", back_populates="employee")
    
    # Indexes
    __table_args__ = (
        Index("idx_employee_department", "department"),
        Index("idx_employee_status", "status"),
    )
    
    def __repr__(self):
        return f"<Employee(id={self.id}, no='{self.employee_no}', name='{self.name}')>"


class SalaryStructure(Base):
    """
    Salary Structure model - 薪资结构表
    Stores salary configuration for each employee.
    """
    __tablename__ = "salary_structures"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), unique=True, nullable=False)
    
    # Base compensation
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    overtime_multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False, default=Decimal("1.5"))
    daily_deduction: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    
    # JSON fields for flexible allowances and deductions
    allowances_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # {"餐补": 500, "交通": 200}
    deductions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # {"社保": 800, "公积金": 600}
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", back_populates="salary_structure")
    
    def __repr__(self):
        return f"<SalaryStructure(employee_id={self.employee_id}, base={self.base_salary})>"


class Attendance(Base):
    """
    Attendance model - 考勤表
    Stores monthly attendance data for each employee.
    """
    __tablename__ = "attendances"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # "2024-01" format
    
    # Attendance data
    work_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    work_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overtime_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    absence_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", back_populates="attendances")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("employee_id", "period", name="uq_attendance_employee_period"),
        Index("idx_attendance_period", "period"),
    )
    
    def __repr__(self):
        return f"<Attendance(employee_id={self.employee_id}, period='{self.period}')>"


class Adjustment(Base):
    """
    Adjustment model - 调整项表
    Stores temporary salary adjustments (bonuses, deductions, etc.)
    """
    __tablename__ = "adjustments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # "2024-01" format
    
    # Adjustment details
    adjustment_type: Mapped[AdjustmentType] = mapped_column(Enum(AdjustmentType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", back_populates="adjustments")
    
    # Indexes
    __table_args__ = (
        Index("idx_adjustment_period", "period"),
        Index("idx_adjustment_employee_period", "employee_id", "period"),
    )
    
    def __repr__(self):
        return f"<Adjustment(employee_id={self.employee_id}, type={self.adjustment_type.value}, amount={self.amount})>"


class PayrollRun(Base):
    """
    Payroll Run model - 工资批次表
    Stores payroll calculation runs.
    """
    __tablename__ = "payroll_runs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # "2024-01" format
    
    # Status
    status: Mapped[PayrollStatus] = mapped_column(Enum(PayrollStatus), default=PayrollStatus.DRAFT)
    
    # Summary statistics (encrypted for security)
    total_employees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    
    # Metadata
    generated_by: Mapped[str] = mapped_column(String(50), nullable=False)
    locked_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    slips = relationship("PayrollSlip", back_populates="payroll_run", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PayrollRun(id={self.id}, period='{self.period}', status={self.status.value})>"


class PayrollSlip(Base):
    """
    Payroll Slip model - 工资条表
    Stores individual payroll calculation results.
    """
    __tablename__ = "payroll_slips"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payroll_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("payroll_runs.id"), nullable=False)
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Calculated amounts
    base_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    overtime_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    allowances_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    adjustments_add: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    
    gross_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    
    absence_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    deductions_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    adjustments_deduct: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    net_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    
    # Detailed breakdown (encrypted JSON)
    details_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    payroll_run = relationship("PayrollRun", back_populates="slips")
    employee = relationship("Employee", back_populates="payroll_slips")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_slip_run_employee"),
        Index("idx_slip_employee", "employee_id"),
    )
    
    def __repr__(self):
        return f"<PayrollSlip(run_id={self.payroll_run_id}, employee_id={self.employee_id}, net={self.net_salary})>"


class AuditLog(Base):
    """
    Audit Log model - 审计日志表
    Stores all sensitive operations for compliance.
    """
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Actor information
    actor: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Result
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="success")  # success, failure, error
    
    # Additional metadata (JSON)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp (cannot be modified)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_audit_created", "created_at"),
        Index("idx_audit_actor_action", "actor", "action"),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, actor='{self.actor}', action='{self.action}')>"
