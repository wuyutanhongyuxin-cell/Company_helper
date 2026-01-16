"""
Database Repositories - 数据访问层
Provides repository pattern for database operations.
"""

import json
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, func, and_, or_

from .models import (
    User, UserRole,
    Employee, EmployeeStatus,
    SalaryStructure,
    Attendance,
    Adjustment, AdjustmentType,
    PayrollRun, PayrollStatus,
    PayrollSlip,
    AuditLog,
)


# =============================================================================
# User Repository
# =============================================================================

class UserRepository:
    """Repository for User operations."""
    
    @staticmethod
    def create(
        session: Session,
        username: str,
        password_hash: str,
        role: UserRole = UserRole.EMPLOYEE,
        employee_id: Optional[int] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            username=username,
            password_hash=password_hash,
            role=role,
            employee_id=employee_id,
        )
        session.add(user)
        session.flush()
        return user
    
    @staticmethod
    def get_by_id(session: Session, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return session.get(User, user_id)
    
    @staticmethod
    def get_by_username(session: Session, username: str) -> Optional[User]:
        """Get user by username."""
        stmt = select(User).where(User.username == username)
        return session.execute(stmt).scalar_one_or_none()
    
    @staticmethod
    def list_all(session: Session, active_only: bool = True) -> List[User]:
        """List all users."""
        stmt = select(User)
        if active_only:
            stmt = stmt.where(User.is_active == True)
        stmt = stmt.order_by(User.username)
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def update_password(session: Session, user_id: int, password_hash: str) -> bool:
        """Update user password."""
        stmt = update(User).where(User.id == user_id).values(password_hash=password_hash)
        result = session.execute(stmt)
        return result.rowcount > 0
    
    @staticmethod
    def update_last_login(session: Session, user_id: int) -> None:
        """Update last login timestamp."""
        stmt = update(User).where(User.id == user_id).values(last_login=datetime.utcnow())
        session.execute(stmt)
    
    @staticmethod
    def set_active(session: Session, user_id: int, is_active: bool) -> bool:
        """Enable or disable a user account."""
        stmt = update(User).where(User.id == user_id).values(is_active=is_active)
        result = session.execute(stmt)
        return result.rowcount > 0
    
    @staticmethod
    def count(session: Session, active_only: bool = True) -> int:
        """Count users."""
        stmt = select(func.count(User.id))
        if active_only:
            stmt = stmt.where(User.is_active == True)
        return session.execute(stmt).scalar() or 0


# =============================================================================
# Employee Repository
# =============================================================================

class EmployeeRepository:
    """Repository for Employee operations."""
    
    @staticmethod
    def create(
        session: Session,
        employee_no: str,
        name: str,
        department: str,
        hire_date: date,
        bank_card_encrypted: Optional[str] = None,
        id_number_encrypted: Optional[str] = None,
    ) -> Employee:
        """Create a new employee."""
        employee = Employee(
            employee_no=employee_no,
            name=name,
            department=department,
            hire_date=hire_date,
            bank_card_encrypted=bank_card_encrypted,
            id_number_encrypted=id_number_encrypted,
        )
        session.add(employee)
        session.flush()
        return employee
    
    @staticmethod
    def get_by_id(session: Session, employee_id: int) -> Optional[Employee]:
        """Get employee by ID."""
        return session.get(Employee, employee_id)
    
    @staticmethod
    def get_by_employee_no(session: Session, employee_no: str) -> Optional[Employee]:
        """Get employee by employee number."""
        stmt = select(Employee).where(Employee.employee_no == employee_no)
        return session.execute(stmt).scalar_one_or_none()
    
    @staticmethod
    def list_all(
        session: Session,
        status: Optional[EmployeeStatus] = None,
        department: Optional[str] = None,
    ) -> List[Employee]:
        """List employees with optional filters."""
        stmt = select(Employee)
        
        if status is not None:
            stmt = stmt.where(Employee.status == status)
        if department is not None:
            stmt = stmt.where(Employee.department == department)
        
        stmt = stmt.order_by(Employee.employee_no)
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def list_active(session: Session) -> List[Employee]:
        """List all active employees."""
        return EmployeeRepository.list_all(session, status=EmployeeStatus.ACTIVE)
    
    @staticmethod
    def update(
        session: Session,
        employee_id: int,
        **kwargs
    ) -> bool:
        """Update employee fields."""
        stmt = update(Employee).where(Employee.id == employee_id).values(**kwargs)
        result = session.execute(stmt)
        return result.rowcount > 0
    
    @staticmethod
    def set_status(session: Session, employee_id: int, status: EmployeeStatus) -> bool:
        """Update employee status."""
        return EmployeeRepository.update(session, employee_id, status=status)
    
    @staticmethod
    def count(session: Session, status: Optional[EmployeeStatus] = None) -> int:
        """Count employees."""
        stmt = select(func.count(Employee.id))
        if status is not None:
            stmt = stmt.where(Employee.status == status)
        return session.execute(stmt).scalar() or 0
    
    @staticmethod
    def count_active(session: Session) -> int:
        """Count active employees."""
        return EmployeeRepository.count(session, EmployeeStatus.ACTIVE)
    
    @staticmethod
    def get_departments(session: Session) -> List[str]:
        """Get list of unique departments."""
        stmt = select(Employee.department).distinct().order_by(Employee.department)
        return list(session.execute(stmt).scalars().all())


# =============================================================================
# Salary Structure Repository
# =============================================================================

class SalaryStructureRepository:
    """Repository for SalaryStructure operations."""
    
    @staticmethod
    def create_or_update(
        session: Session,
        employee_id: int,
        base_salary: Decimal,
        hourly_rate: Decimal,
        overtime_multiplier: Decimal = Decimal("1.5"),
        daily_deduction: Decimal = Decimal("0"),
        allowances: Optional[Dict[str, Any]] = None,
        deductions: Optional[Dict[str, Any]] = None,
    ) -> SalaryStructure:
        """Create or update salary structure for an employee."""
        existing = SalaryStructureRepository.get_by_employee(session, employee_id)
        
        if existing:
            existing.base_salary = base_salary
            existing.hourly_rate = hourly_rate
            existing.overtime_multiplier = overtime_multiplier
            existing.daily_deduction = daily_deduction
            existing.allowances_json = json.dumps(allowances) if allowances else None
            existing.deductions_json = json.dumps(deductions) if deductions else None
            session.flush()
            return existing
        else:
            structure = SalaryStructure(
                employee_id=employee_id,
                base_salary=base_salary,
                hourly_rate=hourly_rate,
                overtime_multiplier=overtime_multiplier,
                daily_deduction=daily_deduction,
                allowances_json=json.dumps(allowances) if allowances else None,
                deductions_json=json.dumps(deductions) if deductions else None,
            )
            session.add(structure)
            session.flush()
            return structure
    
    @staticmethod
    def get_by_employee(session: Session, employee_id: int) -> Optional[SalaryStructure]:
        """Get salary structure for an employee."""
        stmt = select(SalaryStructure).where(SalaryStructure.employee_id == employee_id)
        return session.execute(stmt).scalar_one_or_none()
    
    @staticmethod
    def delete_by_employee(session: Session, employee_id: int) -> bool:
        """Delete salary structure for an employee."""
        stmt = delete(SalaryStructure).where(SalaryStructure.employee_id == employee_id)
        result = session.execute(stmt)
        return result.rowcount > 0


# =============================================================================
# Attendance Repository
# =============================================================================

class AttendanceRepository:
    """Repository for Attendance operations."""
    
    @staticmethod
    def create(
        session: Session,
        employee_id: int,
        period: str,
        work_days: int = 0,
        work_hours: int = 0,
        overtime_hours: Decimal = Decimal("0"),
        absence_days: Decimal = Decimal("0"),
    ) -> Attendance:
        """Create attendance record."""
        attendance = Attendance(
            employee_id=employee_id,
            period=period,
            work_days=work_days,
            work_hours=work_hours,
            overtime_hours=overtime_hours,
            absence_days=absence_days,
        )
        session.add(attendance)
        session.flush()
        return attendance
    
    @staticmethod
    def get_or_create(
        session: Session,
        employee_id: int,
        period: str,
        **kwargs
    ) -> Tuple[Attendance, bool]:
        """Get existing or create new attendance record."""
        existing = AttendanceRepository.get_by_employee_period(session, employee_id, period)
        if existing:
            # Update if exists
            for key, value in kwargs.items():
                setattr(existing, key, value)
            session.flush()
            return existing, False
        else:
            attendance = AttendanceRepository.create(session, employee_id, period, **kwargs)
            return attendance, True
    
    @staticmethod
    def get_by_employee_period(session: Session, employee_id: int, period: str) -> Optional[Attendance]:
        """Get attendance for an employee in a specific period."""
        stmt = select(Attendance).where(
            and_(
                Attendance.employee_id == employee_id,
                Attendance.period == period
            )
        )
        return session.execute(stmt).scalar_one_or_none()
    
    @staticmethod
    def list_by_period(session: Session, period: str) -> List[Attendance]:
        """List all attendance records for a period."""
        stmt = select(Attendance).where(Attendance.period == period)
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def list_by_employee(session: Session, employee_id: int) -> List[Attendance]:
        """List all attendance records for an employee."""
        stmt = select(Attendance).where(Attendance.employee_id == employee_id).order_by(Attendance.period.desc())
        return list(session.execute(stmt).scalars().all())


# =============================================================================
# Adjustment Repository
# =============================================================================

class AdjustmentRepository:
    """Repository for Adjustment operations."""
    
    @staticmethod
    def create(
        session: Session,
        employee_id: int,
        period: str,
        adjustment_type: AdjustmentType,
        amount: Decimal,
        reason: Optional[str] = None,
    ) -> Adjustment:
        """Create adjustment record."""
        adjustment = Adjustment(
            employee_id=employee_id,
            period=period,
            adjustment_type=adjustment_type,
            amount=amount,
            reason=reason,
        )
        session.add(adjustment)
        session.flush()
        return adjustment
    
    @staticmethod
    def list_by_employee_period(session: Session, employee_id: int, period: str) -> List[Adjustment]:
        """List adjustments for an employee in a specific period."""
        stmt = select(Adjustment).where(
            and_(
                Adjustment.employee_id == employee_id,
                Adjustment.period == period
            )
        )
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def list_by_period(session: Session, period: str) -> List[Adjustment]:
        """List all adjustments for a period."""
        stmt = select(Adjustment).where(Adjustment.period == period)
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def sum_by_employee_period(session: Session, employee_id: int, period: str) -> Tuple[Decimal, Decimal]:
        """Get sum of additions and deductions for an employee in a period."""
        adjustments = AdjustmentRepository.list_by_employee_period(session, employee_id, period)
        
        add_total = Decimal("0")
        deduct_total = Decimal("0")
        
        for adj in adjustments:
            if adj.adjustment_type == AdjustmentType.ADD:
                add_total += adj.amount
            else:
                deduct_total += adj.amount
        
        return add_total, deduct_total
    
    @staticmethod
    def delete_by_id(session: Session, adjustment_id: int) -> bool:
        """Delete an adjustment."""
        stmt = delete(Adjustment).where(Adjustment.id == adjustment_id)
        result = session.execute(stmt)
        return result.rowcount > 0


# =============================================================================
# Payroll Run Repository
# =============================================================================

class PayrollRunRepository:
    """Repository for PayrollRun operations."""
    
    @staticmethod
    def create(
        session: Session,
        period: str,
        generated_by: str,
    ) -> PayrollRun:
        """Create a new payroll run."""
        run = PayrollRun(
            period=period,
            generated_by=generated_by,
            status=PayrollStatus.DRAFT,
        )
        session.add(run)
        session.flush()
        return run
    
    @staticmethod
    def get_by_id(session: Session, run_id: int) -> Optional[PayrollRun]:
        """Get payroll run by ID."""
        return session.get(PayrollRun, run_id)
    
    @staticmethod
    def get_by_period(session: Session, period: str) -> Optional[PayrollRun]:
        """Get the latest payroll run for a period."""
        stmt = select(PayrollRun).where(PayrollRun.period == period).order_by(PayrollRun.created_at.desc())
        return session.execute(stmt).scalars().first()
    
    @staticmethod
    def list_all(session: Session, limit: int = 50) -> List[PayrollRun]:
        """List all payroll runs."""
        stmt = select(PayrollRun).order_by(PayrollRun.created_at.desc()).limit(limit)
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def update_totals(
        session: Session,
        run_id: int,
        total_employees: int,
        total_gross: Decimal,
        total_deductions: Decimal,
        total_net: Decimal,
    ) -> bool:
        """Update payroll run totals."""
        stmt = update(PayrollRun).where(PayrollRun.id == run_id).values(
            total_employees=total_employees,
            total_gross=total_gross,
            total_deductions=total_deductions,
            total_net=total_net,
        )
        result = session.execute(stmt)
        return result.rowcount > 0
    
    @staticmethod
    def lock(session: Session, run_id: int, locked_by: str) -> bool:
        """Lock a payroll run."""
        stmt = update(PayrollRun).where(
            and_(
                PayrollRun.id == run_id,
                PayrollRun.status == PayrollStatus.DRAFT
            )
        ).values(
            status=PayrollStatus.LOCKED,
            locked_by=locked_by,
            locked_at=datetime.utcnow(),
        )
        result = session.execute(stmt)
        return result.rowcount > 0
    
    @staticmethod
    def unlock(session: Session, run_id: int) -> bool:
        """Unlock a payroll run."""
        stmt = update(PayrollRun).where(
            and_(
                PayrollRun.id == run_id,
                PayrollRun.status == PayrollStatus.LOCKED
            )
        ).values(
            status=PayrollStatus.DRAFT,
            locked_by=None,
            locked_at=None,
        )
        result = session.execute(stmt)
        return result.rowcount > 0
    
    @staticmethod
    def delete(session: Session, run_id: int) -> bool:
        """Delete a payroll run (only if in draft status)."""
        stmt = delete(PayrollRun).where(
            and_(
                PayrollRun.id == run_id,
                PayrollRun.status == PayrollStatus.DRAFT
            )
        )
        result = session.execute(stmt)
        return result.rowcount > 0


# =============================================================================
# Payroll Slip Repository
# =============================================================================

class PayrollSlipRepository:
    """Repository for PayrollSlip operations."""
    
    @staticmethod
    def create(
        session: Session,
        payroll_run_id: int,
        employee_id: int,
        base_salary: Decimal = Decimal("0"),
        overtime_pay: Decimal = Decimal("0"),
        allowances_total: Decimal = Decimal("0"),
        adjustments_add: Decimal = Decimal("0"),
        gross_salary: Decimal = Decimal("0"),
        absence_deduction: Decimal = Decimal("0"),
        deductions_total: Decimal = Decimal("0"),
        adjustments_deduct: Decimal = Decimal("0"),
        tax: Decimal = Decimal("0"),
        total_deductions: Decimal = Decimal("0"),
        net_salary: Decimal = Decimal("0"),
        details_encrypted: Optional[str] = None,
    ) -> PayrollSlip:
        """Create a payroll slip."""
        slip = PayrollSlip(
            payroll_run_id=payroll_run_id,
            employee_id=employee_id,
            base_salary=base_salary,
            overtime_pay=overtime_pay,
            allowances_total=allowances_total,
            adjustments_add=adjustments_add,
            gross_salary=gross_salary,
            absence_deduction=absence_deduction,
            deductions_total=deductions_total,
            adjustments_deduct=adjustments_deduct,
            tax=tax,
            total_deductions=total_deductions,
            net_salary=net_salary,
            details_encrypted=details_encrypted,
        )
        session.add(slip)
        session.flush()
        return slip
    
    @staticmethod
    def list_by_run(session: Session, run_id: int) -> List[PayrollSlip]:
        """List all slips for a payroll run."""
        stmt = select(PayrollSlip).where(PayrollSlip.payroll_run_id == run_id)
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def get_by_run_employee(session: Session, run_id: int, employee_id: int) -> Optional[PayrollSlip]:
        """Get slip for a specific employee in a run."""
        stmt = select(PayrollSlip).where(
            and_(
                PayrollSlip.payroll_run_id == run_id,
                PayrollSlip.employee_id == employee_id
            )
        )
        return session.execute(stmt).scalar_one_or_none()
    
    @staticmethod
    def delete_by_run(session: Session, run_id: int) -> int:
        """Delete all slips for a payroll run."""
        stmt = delete(PayrollSlip).where(PayrollSlip.payroll_run_id == run_id)
        result = session.execute(stmt)
        return result.rowcount


# =============================================================================
# Audit Log Repository
# =============================================================================

class AuditLogRepository:
    """Repository for AuditLog operations (append-only)."""
    
    @staticmethod
    def create(
        session: Session,
        actor: str,
        action: str,
        result: str = "success",
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Create an audit log entry."""
        log = AuditLog(
            actor=actor,
            action=action,
            result=result,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        session.add(log)
        session.flush()
        return log
    
    @staticmethod
    def list_all(
        session: Session,
        limit: int = 100,
        offset: int = 0,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditLog]:
        """List audit logs with filters."""
        stmt = select(AuditLog)
        
        if actor:
            stmt = stmt.where(AuditLog.actor == actor)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)
        
        stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        return list(session.execute(stmt).scalars().all())
    
    @staticmethod
    def count(session: Session) -> int:
        """Count total audit logs."""
        stmt = select(func.count(AuditLog.id))
        return session.execute(stmt).scalar() or 0
    
    @staticmethod
    def get_recent(session: Session, limit: int = 10) -> List[AuditLog]:
        """Get most recent audit logs."""
        return AuditLogRepository.list_all(session, limit=limit)
