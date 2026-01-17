"""
Business Services - 业务服务层
Provides business logic for the payroll management system.
"""

import os
import re
import json
import hashlib
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.db import (
    session_scope,
    User, UserRole,
    Employee, EmployeeStatus,
    SalaryStructure,
    Attendance,
    Adjustment, AdjustmentType,
    PayrollRun, PayrollStatus,
    PayrollSlip,
    AuditLog,
    UserRepository,
    EmployeeRepository,
    SalaryStructureRepository,
    AttendanceRepository,
    AdjustmentRepository,
    PayrollRunRepository,
    PayrollSlipRepository,
    AuditLogRepository,
)


# =============================================================================
# Singleton Accessors (with lazy import to avoid circular dependencies)
# =============================================================================

def get_encryption_manager():
    """Get encryption manager (lazy import)."""
    from app.security import get_encryption_manager as _get_em
    # Try to get master_key from Streamlit session_state
    try:
        import streamlit as st
        master_key = st.session_state.get("master_key")
        if master_key:
            return _get_em(master_key)
    except:
        pass
    return _get_em()


def get_password_manager():
    """Get password manager (lazy import)."""
    from app.security import get_password_manager as _get_pm
    return _get_pm()


def get_rate_limiter():
    """Get rate limiter (lazy import)."""
    from app.security import get_rate_limiter as _get_rl
    return _get_rl()


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class PayrollSummary:
    """Summary of a payroll run."""
    total_employees: int
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal


# =============================================================================
# Auth Service
# =============================================================================

class AuthService:
    """
    Authentication service.
    用户认证服务
    """
    
    @staticmethod
    def login(username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Authenticate a user.

        Args:
            username: The username to authenticate
            password: The password to verify

        Returns:
            Tuple of (success, user_data_dict, message)
        """
        rate_limiter = get_rate_limiter()

        # Check rate limiting
        is_locked, remaining = rate_limiter.is_locked(username)
        if is_locked:
            return False, None, f"账户已锁定，请 {remaining} 秒后重试"

        with session_scope() as session:
            user = UserRepository.get_by_username(session, username)
            pm = get_password_manager()

            # 防止时序攻击：无论用户是否存在都执行密码验证
            if user is None:
                # 使用假哈希值进行验证，确保执行时间一致
                dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdHNhbHQxMjM0NTY3OA$qL0jB5Kz9X0mC3nP8rE4wK2vF5tU7yH6sD1aB3cE4fG"
                pm.verify_password(password, dummy_hash)
                rate_limiter.record_attempt(username, success=False)
                return False, None, "用户名或密码错误"

            # Verify password (真实验证)
            password_valid = pm.verify_password(password, user.password_hash)

            # 检查账户状态
            if not user.is_active:
                rate_limiter.record_attempt(username, success=False)
                return False, None, "用户名或密码错误"  # 统一错误消息，不泄露账户状态

            if not password_valid:
                rate_limiter.record_attempt(username, success=False)
                remaining_attempts = rate_limiter.get_remaining_attempts(username)
                return False, None, f"用户名或密码错误（剩余 {remaining_attempts} 次尝试）"

            # Success - extract user data while still in session
            user_data = {
                "id": user.id,
                "username": user.username,
                "role": user.role.value,
                "is_active": user.is_active,
            }

            rate_limiter.record_attempt(username, success=True)
            UserRepository.update_last_login(session, user.id)

            # Log the login
            AuditLogRepository.create(
                session,
                actor=username,
                action="login",
                result="success",
            )

            return True, user_data, "登录成功"
    
    @staticmethod
    def create_user(
        username: str,
        password: str,
        role: UserRole,
        actor: str,
        employee_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Create a new user.
        
        Args:
            username: New username
            password: New password
            role: User role
            actor: Username of the person creating this user
            employee_id: Optional linked employee ID
            
        Returns:
            Tuple of (success, message)
        """
        if not username or len(username) < 3:
            return False, "用户名至少需要3个字符"
        
        if not password or len(password) < 8:
            return False, "密码至少需要8个字符"
        
        pm = get_password_manager()
        password_hash = pm.hash_password(password)
        
        with session_scope() as session:
            # Check if username exists
            existing = UserRepository.get_by_username(session, username)
            if existing:
                return False, "用户名已存在"
            
            user = UserRepository.create(
                session,
                username=username,
                password_hash=password_hash,
                role=role,
                employee_id=employee_id,
            )
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="create_user",
                result="success",
                resource_type="user",
                resource_id=user.id,
            )
            
            return True, f"用户 {username} 创建成功"
    
    @staticmethod
    def change_password(user_id: int, new_password: str, actor: str) -> Tuple[bool, str]:
        """Change a user's password."""
        if not new_password or len(new_password) < 8:
            return False, "密码至少需要8个字符"
        
        pm = get_password_manager()
        password_hash = pm.hash_password(new_password)
        
        with session_scope() as session:
            success = UserRepository.update_password(session, user_id, password_hash)
            
            if success:
                AuditLogRepository.create(
                    session,
                    actor=actor,
                    action="change_password",
                    result="success",
                    resource_type="user",
                    resource_id=user_id,
                )
                return True, "密码修改成功"
            else:
                return False, "用户不存在"


# =============================================================================
# Employee Service
# =============================================================================

class EmployeeService:
    """
    Employee management service.
    员工管理服务
    """
    
    @staticmethod
    def create_employee(data: Dict[str, Any], actor: str) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new employee.
        
        Args:
            data: Employee data dictionary
            actor: Username of the person creating this employee
            
        Returns:
            Tuple of (success, message, employee_id)
        """
        employee_no = data.get("employee_no", "").strip()
        name = data.get("name", "").strip()
        department = data.get("department", "").strip()
        hire_date = data.get("hire_date")
        bank_card = data.get("bank_card", "")
        id_number = data.get("id_number", "")
        
        # Validation
        if not employee_no:
            return False, "员工编号无效", None
        if not name:
            return False, "员工姓名无效", None
        # 部门是可选的，默认为"未分配"
        if not department:
            department = "未分配"
        if not hire_date:
            return False, "入职日期无效", None
        
        # Encrypt sensitive data
        em = get_encryption_manager()
        bank_card_encrypted = em.encrypt(bank_card) if bank_card else None
        id_number_encrypted = em.encrypt(id_number) if id_number else None
        
        with session_scope() as session:
            # Check for duplicate
            existing = EmployeeRepository.get_by_employee_no(session, employee_no)
            if existing:
                return False, f"员工编号 {employee_no} 已存在", None
            
            employee = EmployeeRepository.create(
                session,
                employee_no=employee_no,
                name=name,
                department=department,
                hire_date=hire_date,
                bank_card_encrypted=bank_card_encrypted,
                id_number_encrypted=id_number_encrypted,
            )
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="create_employee",
                result="success",
                resource_type="employee",
                resource_id=employee.id,
            )
            
            return True, f"员工 {name} 创建成功", employee.id
    
    @staticmethod
    def get_employee_with_sensitive_data(
        employee_id: int,
        can_view_sensitive: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get employee data with optional decryption of sensitive fields.
        
        Args:
            employee_id: Employee ID
            can_view_sensitive: Whether to decrypt and show sensitive data
            
        Returns:
            Employee data dictionary or None
        """
        with session_scope() as session:
            employee = EmployeeRepository.get_by_id(session, employee_id)
            if not employee:
                return None
            
            em = get_encryption_manager()
            
            result = {
                "id": employee.id,
                "employee_no": employee.employee_no,
                "name": employee.name,
                "department": employee.department,
                "hire_date": employee.hire_date,
                "status": employee.status.value,
            }
            
            if can_view_sensitive:
                # Decrypt and show full values
                result["bank_card"] = em.decrypt(employee.bank_card_encrypted) if employee.bank_card_encrypted else None
                result["id_number"] = em.decrypt(employee.id_number_encrypted) if employee.id_number_encrypted else None
            else:
                # Redact sensitive values
                bank_card = em.decrypt(employee.bank_card_encrypted) if employee.bank_card_encrypted else None
                id_number = em.decrypt(employee.id_number_encrypted) if employee.id_number_encrypted else None
                result["bank_card"] = em.redact_sensitive(bank_card) if bank_card else None
                result["id_number"] = em.redact_sensitive(id_number) if id_number else None
            
            return result
    
    @staticmethod
    def list_employees(status: Optional[EmployeeStatus] = None) -> List[Dict[str, Any]]:
        """
        List all employees (without sensitive data).
        
        Args:
            status: Optional status filter
            
        Returns:
            List of employee dictionaries
        """
        with session_scope() as session:
            if status:
                employees = EmployeeRepository.list_all(session, status=status)
            else:
                employees = EmployeeRepository.list_all(session)
            
            return [
                {
                    "id": emp.id,
                    "employee_no": emp.employee_no,
                    "name": emp.name,
                    "department": emp.department,
                    "hire_date": emp.hire_date,
                    "status": emp.status.value,
                }
                for emp in employees
            ]
    
    @staticmethod
    def count_active() -> int:
        """Count active employees."""
        with session_scope() as session:
            return EmployeeRepository.count_active(session)
    
    @staticmethod
    def update_employee(employee_id: int, data: Dict[str, Any], actor: str) -> Tuple[bool, str]:
        """Update employee data."""
        with session_scope() as session:
            employee = EmployeeRepository.get_by_id(session, employee_id)
            if not employee:
                return False, "员工不存在"
            
            # Update basic fields
            update_data = {}
            if "name" in data:
                update_data["name"] = data["name"]
            if "department" in data:
                update_data["department"] = data["department"]
            if "status" in data:
                update_data["status"] = data["status"]
            
            # Encrypt sensitive fields if provided
            em = get_encryption_manager()
            if "bank_card" in data:
                update_data["bank_card_encrypted"] = em.encrypt(data["bank_card"]) if data["bank_card"] else None
            if "id_number" in data:
                update_data["id_number_encrypted"] = em.encrypt(data["id_number"]) if data["id_number"] else None
            
            if update_data:
                EmployeeRepository.update(session, employee_id, **update_data)
                
                AuditLogRepository.create(
                    session,
                    actor=actor,
                    action="update_employee",
                    result="success",
                    resource_type="employee",
                    resource_id=employee_id,
                )
            
            return True, "员工信息更新成功"


# =============================================================================
# Salary Structure Service
# =============================================================================

class SalaryStructureService:
    """
    Salary structure management service.
    薪资结构管理服务
    """
    
    @staticmethod
    def create_or_update(
        employee_id: int,
        data: Dict[str, Any],
        actor: str
    ) -> Tuple[bool, str]:
        """
        Create or update salary structure for an employee.
        
        Args:
            employee_id: Employee ID
            data: Salary structure data
            actor: Username performing this action
            
        Returns:
            Tuple of (success, message)
        """
        base_salary = Decimal(str(data.get("base_salary", 0)))
        hourly_rate = Decimal(str(data.get("hourly_rate", 0)))
        overtime_multiplier = Decimal(str(data.get("overtime_multiplier", 1.5)))
        daily_deduction = Decimal(str(data.get("daily_deduction", 0)))
        allowances = data.get("allowances", {})
        deductions = data.get("deductions", {})
        
        with session_scope() as session:
            employee = EmployeeRepository.get_by_id(session, employee_id)
            if not employee:
                return False, "员工不存在"
            
            SalaryStructureRepository.create_or_update(
                session,
                employee_id=employee_id,
                base_salary=base_salary,
                hourly_rate=hourly_rate,
                overtime_multiplier=overtime_multiplier,
                daily_deduction=daily_deduction,
                allowances=allowances,
                deductions=deductions,
            )
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="update_salary_structure",
                result="success",
                resource_type="salary_structure",
                resource_id=employee_id,
            )
            
            return True, "薪资结构更新成功"
    
    @staticmethod
    def get_by_employee(employee_id: int) -> Optional[Dict[str, Any]]:
        """Get salary structure for an employee."""
        with session_scope() as session:
            structure = SalaryStructureRepository.get_by_employee(session, employee_id)
            if not structure:
                return None
            
            return {
                "id": structure.id,
                "employee_id": structure.employee_id,
                "base_salary": structure.base_salary,
                "hourly_rate": structure.hourly_rate,
                "overtime_multiplier": structure.overtime_multiplier,
                "daily_deduction": structure.daily_deduction,
                "allowances": json.loads(structure.allowances_json) if structure.allowances_json else {},
                "deductions": json.loads(structure.deductions_json) if structure.deductions_json else {},
            }


# =============================================================================
# Payroll Service
# =============================================================================

class PayrollService:
    """
    Payroll calculation and management service.
    工资计算与管理服务
    """
    
    PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
    
    @staticmethod
    def validate_period(period: str) -> bool:
        """Validate period format (YYYY-MM)."""
        return bool(PayrollService.PERIOD_PATTERN.match(period))
    
    @staticmethod
    def generate_payroll(period: str, actor: str) -> Tuple[bool, str, Optional[PayrollSummary]]:
        """
        Generate payroll for a period.
        
        Args:
            period: Period in YYYY-MM format
            actor: Username generating payroll
            
        Returns:
            Tuple of (success, message, summary)
        """
        if not PayrollService.validate_period(period):
            return False, "期间格式无效，请使用 YYYY-MM 格式", None
        
        with session_scope() as session:
            # Get active employees
            employees = EmployeeRepository.list_active(session)
            if not employees:
                return False, "没有在职员工", None
            
            # Create payroll run
            run = PayrollRunRepository.create(session, period, actor)
            
            total_gross = Decimal("0")
            total_deductions = Decimal("0")
            total_net = Decimal("0")
            processed_count = 0
            
            employees_without_attendance = []

            for employee in employees:
                # Get salary structure
                structure = SalaryStructureRepository.get_by_employee(session, employee.id)
                if not structure:
                    continue

                # Get attendance - 必须存在考勤记录
                attendance = AttendanceRepository.get_by_employee_period(session, employee.id, period)
                if not attendance:
                    employees_without_attendance.append(f"{employee.name}({employee.employee_no})")
                    continue  # 跳过没有考勤记录的员工

                # Get adjustments
                adj_add, adj_deduct = AdjustmentRepository.sum_by_employee_period(session, employee.id, period)

                # Calculate payroll
                slip_data = PayrollService._calculate_slip(structure, attendance, adj_add, adj_deduct)

                # Create slip
                PayrollSlipRepository.create(
                    session,
                    payroll_run_id=run.id,
                    employee_id=employee.id,
                    **slip_data
                )

                total_gross += slip_data["gross_salary"]
                total_deductions += slip_data["total_deductions"]
                total_net += slip_data["net_salary"]
                processed_count += 1

            # 如果有员工缺少考勤记录，添加到审计日志
            if employees_without_attendance:
                warning_msg = f"以下员工没有考勤记录，已跳过: {', '.join(employees_without_attendance[:10])}"
                if len(employees_without_attendance) > 10:
                    warning_msg += f" 等共 {len(employees_without_attendance)} 人"
                AuditLogRepository.create(
                    session,
                    actor=actor,
                    action="generate_payroll_warning",
                    result="success",
                    resource_type="payroll_run",
                    resource_id=run.id,
                    metadata={"warning": warning_msg, "skipped_employees": len(employees_without_attendance)},
                )
            
            # Update run totals
            PayrollRunRepository.update_totals(
                session,
                run.id,
                total_employees=processed_count,
                total_gross=total_gross,
                total_deductions=total_deductions,
                total_net=total_net,
            )
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="generate_payroll",
                result="success",
                resource_type="payroll_run",
                resource_id=run.id,
                metadata={"period": period, "employees": processed_count},
            )
            
            summary = PayrollSummary(
                total_employees=processed_count,
                total_gross=total_gross,
                total_deductions=total_deductions,
                total_net=total_net,
            )
            
            return True, f"工资生成成功，共处理 {processed_count} 名员工", summary
    
    @staticmethod
    def _calculate_slip(
        structure: SalaryStructure,
        attendance: Optional[Attendance],
        adj_add: Decimal,
        adj_deduct: Decimal
    ) -> Dict[str, Decimal]:
        """Calculate individual payroll slip."""
        # 定义精度量化函数
        def quantize_money(value: Decimal) -> Decimal:
            """量化金额到2位小数"""
            return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        base_salary = quantize_money(structure.base_salary)

        # Overtime pay
        overtime_hours = Decimal(str(attendance.overtime_hours)) if attendance else Decimal("0")
        overtime_pay = quantize_money(overtime_hours * structure.hourly_rate * structure.overtime_multiplier)

        # Allowances - 确保每个津贴都量化
        allowances = json.loads(structure.allowances_json) if structure.allowances_json else {}
        allowances_total = quantize_money(sum(Decimal(str(v)) for v in allowances.values()))

        # 确保调整项也量化
        adj_add = quantize_money(adj_add)

        # Gross salary - 所有项都已量化，再次量化以确保精度
        gross_salary = quantize_money(base_salary + overtime_pay + allowances_total + adj_add)

        # Absence deduction
        absence_days = Decimal(str(attendance.absence_days)) if attendance else Decimal("0")
        absence_deduction = quantize_money(absence_days * structure.daily_deduction)

        # Fixed deductions - 确保每个扣款都量化
        deductions = json.loads(structure.deductions_json) if structure.deductions_json else {}
        deductions_total = quantize_money(sum(Decimal(str(v)) for v in deductions.values()))

        # 确保调整扣款也量化
        adj_deduct = quantize_money(adj_deduct)

        # Tax (simplified - 0 for now, can be expanded)
        tax = Decimal("0")

        # Total deductions - 所有项都已量化，再次量化以确保精度
        total_deductions = quantize_money(absence_deduction + deductions_total + adj_deduct + tax)

        # Net salary - 最终量化
        net_salary = quantize_money(gross_salary - total_deductions)

        return {
            "base_salary": base_salary,
            "overtime_pay": overtime_pay,
            "allowances_total": allowances_total,
            "adjustments_add": adj_add,
            "gross_salary": gross_salary,
            "absence_deduction": absence_deduction,
            "deductions_total": deductions_total,
            "adjustments_deduct": adj_deduct,
            "tax": tax,
            "total_deductions": total_deductions,
            "net_salary": net_salary,
        }
    
    @staticmethod
    def list_payroll_runs(limit: int = 50) -> List[Dict[str, Any]]:
        """List all payroll runs."""
        with session_scope() as session:
            runs = PayrollRunRepository.list_all(session, limit)
            return [
                {
                    "id": run.id,
                    "period": run.period,
                    "status": run.status.value,
                    "total_employees": run.total_employees,
                    "total_gross": float(run.total_gross),
                    "total_net": float(run.total_net),
                    "generated_by": run.generated_by,
                    "created_at": run.created_at.isoformat(),
                    "locked_at": run.locked_at.isoformat() if run.locked_at else None,
                }
                for run in runs
            ]
    
    @staticmethod
    def get_payroll_slips(run_id: int) -> List[Dict[str, Any]]:
        """Get all payroll slips for a run."""
        with session_scope() as session:
            slips = PayrollSlipRepository.list_by_run(session, run_id)
            result = []
            for slip in slips:
                employee = EmployeeRepository.get_by_id(session, slip.employee_id)
                result.append({
                    "id": slip.id,
                    "employee_id": slip.employee_id,
                    "employee_no": employee.employee_no if employee else "",
                    "employee_name": employee.name if employee else "",
                    "department": employee.department if employee else "",
                    "base_salary": float(slip.base_salary),
                    "overtime_pay": float(slip.overtime_pay),
                    "allowances_total": float(slip.allowances_total),
                    "adjustments_add": float(slip.adjustments_add),
                    "gross_salary": float(slip.gross_salary),
                    "absence_deduction": float(slip.absence_deduction),
                    "deductions_total": float(slip.deductions_total),
                    "adjustments_deduct": float(slip.adjustments_deduct),
                    "tax": float(slip.tax),
                    "total_deductions": float(slip.total_deductions),
                    "net_salary": float(slip.net_salary),
                })
            return result
    
    @staticmethod
    def lock_payroll(run_id: int, actor: str) -> Tuple[bool, str]:
        """Lock a payroll run."""
        with session_scope() as session:
            run = PayrollRunRepository.get_by_id(session, run_id)
            if not run:
                return False, "工资批次不存在"
            
            if run.status == PayrollStatus.LOCKED:
                return False, "工资批次已锁定"
            
            success = PayrollRunRepository.lock(session, run_id, actor)
            
            if success:
                AuditLogRepository.create(
                    session,
                    actor=actor,
                    action="lock_payroll",
                    result="success",
                    resource_type="payroll_run",
                    resource_id=run_id,
                )
                return True, "工资批次已锁定"
            else:
                return False, "锁定失败"
    
    @staticmethod
    def unlock_payroll(run_id: int, actor: str, reason: str, confirmed: bool = False) -> Tuple[bool, str]:
        """
        Unlock a payroll run (requires confirmation and reason).

        Args:
            run_id: Payroll run ID
            actor: Username performing the unlock
            reason: Reason for unlocking (required, min 10 characters)
            confirmed: Must be True to proceed

        Returns:
            Tuple of (success, message)
        """
        if not confirmed:
            return False, "解锁需要确认，请设置 confirmed=True"

        # 强制要求提供解锁理由
        if not reason or len(reason.strip()) < 10:
            return False, "必须提供解锁理由（至少10个字符）"

        with session_scope() as session:
            run = PayrollRunRepository.get_by_id(session, run_id)
            if not run:
                return False, "工资批次不存在"

            if run.status != PayrollStatus.LOCKED:
                return False, "工资批次未锁定"

            # 记录解锁前的状态，用于审计追踪
            original_data = {
                "period": run.period,
                "total_employees": run.total_employees,
                "total_gross": float(run.total_gross),
                "total_net": float(run.total_net),
                "locked_by": run.locked_by,
                "locked_at": run.locked_at.isoformat() if run.locked_at else None,
            }

            success = PayrollRunRepository.unlock(session, run_id)

            if success:
                # 创建高优先级审计日志
                AuditLogRepository.create(
                    session,
                    actor=actor,
                    action="unlock_payroll_critical",
                    result="success",
                    resource_type="payroll_run",
                    resource_id=run_id,
                    metadata={
                        "warning": "!!! 工资批次已解锁，允许修改 !!!",
                        "reason": reason.strip(),
                        "original_data": original_data,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
                return True, f"工资批次已解锁（理由: {reason.strip()[:50]}）"
            else:
                return False, "解锁失败"


# =============================================================================
# Import Service
# =============================================================================

class ImportService:
    """
    Data import service.
    数据导入服务
    """
    
    # Column mapping for Chinese headers (支持多种列名变体)
    EMPLOYEE_COLUMNS = {
        "员工编号": "employee_no",
        "工号": "employee_no",
        "编号": "employee_no",
        "姓名": "name",
        "名字": "name",
        "部门": "department",
        "岗位": "department",  # 岗位也作为部门处理
        "入职日期": "hire_date",
        "入职时间": "hire_date",
        "银行卡号": "bank_card",
        "银行卡": "bank_card",
        "身份证号": "id_number",
        "身份证": "id_number",
        "联系电话": "phone",
        "电话": "phone",
        "开户行": "bank_name",
        "状态": "status",
    }
    
    SALARY_COLUMNS = {
        "员工编号": "employee_no",
        "工号": "employee_no",
        "基本工资": "base_salary",
        "时薪": "hourly_rate",
        "加班倍率": "overtime_multiplier",
        "日扣款标准": "daily_deduction",
        "津贴(JSON)": "allowances_json",
        "固定扣款(JSON)": "deductions_json",
    }
    
    ATTENDANCE_COLUMNS = {
        "员工编号": "employee_no",
        "工号": "employee_no",
        "期间": "period",
        "月份": "period",
        "工作天数": "work_days",
        "出勤天数": "work_days",
        "加班小时": "overtime_hours",
        "加班时长": "overtime_hours",
        "缺勤天数": "absence_days",
    }
    
    ADJUSTMENT_COLUMNS = {
        "员工编号": "employee_no",
        "工号": "employee_no",
        "期间": "period",
        "月份": "period",
        "类型": "type",
        "金额": "amount",
        "原因": "reason",
        "备注": "reason",
    }
    
    @staticmethod
    def _rename_columns(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Rename DataFrame columns using mapping."""
        reverse_mapping = {v: k for k, v in mapping.items()}
        columns_to_rename = {}
        for col in df.columns:
            if col in mapping:
                columns_to_rename[col] = mapping[col]
            elif col in reverse_mapping:
                pass  # Already in English
        return df.rename(columns=columns_to_rename)
    
    @staticmethod
    def import_employees(df: pd.DataFrame, actor: str) -> Tuple[bool, str, int]:
        """
        Import employees from DataFrame with improved error handling.

        Args:
            df: DataFrame with employee data
            actor: Username performing import

        Returns:
            Tuple of (success, message, count)
        """
        # 预先检查加密管理器是否可用
        try:
            get_encryption_manager()
        except ValueError as e:
            return False, f"导入失败: 加密服务未初始化，请确保您已登录并输入了正确的主密钥", 0
        except Exception as e:
            return False, f"导入失败: 加密服务错误 - {str(e)}", 0

        df = ImportService._rename_columns(df, ImportService.EMPLOYEE_COLUMNS)

        imported_count = 0
        errors = []
        total_rows = len(df)

        for idx, row in df.iterrows():
            try:
                hire_date = row.get("hire_date")
                if isinstance(hire_date, str):
                    hire_date = datetime.strptime(hire_date, "%Y-%m-%d").date()
                elif hasattr(hire_date, "date"):
                    hire_date = hire_date.date()

                data = {
                    "employee_no": str(row.get("employee_no", "")).strip(),
                    "name": str(row.get("name", "")).strip(),
                    "department": str(row.get("department", "")).strip(),
                    "hire_date": hire_date,
                    "bank_card": str(row.get("bank_card", "")).strip() if pd.notna(row.get("bank_card")) else "",
                    "id_number": str(row.get("id_number", "")).strip() if pd.notna(row.get("id_number")) else "",
                }

                success, message, _ = EmployeeService.create_employee(data, actor)
                if success:
                    imported_count += 1
                else:
                    errors.append(f"行 {idx + 2}: {message}")
            except Exception as e:
                errors.append(f"行 {idx + 2}: {str(e)}")

        # 改进的结果报告
        failed_count = len(errors)
        if imported_count == 0:
            # 全部失败
            error_summary = "; ".join(errors[:10])
            if failed_count > 10:
                error_summary += f"... 等共 {failed_count} 个错误"
            return False, f"导入失败，所有 {total_rows} 行都失败: {error_summary}", 0
        elif failed_count > 0:
            # 部分成功
            error_summary = "; ".join(errors[:5])
            if failed_count > 5:
                error_summary += f"... 等共 {failed_count} 个错误"
            return True, f"部分成功：导入 {imported_count}/{total_rows} 名员工，{failed_count} 行失败。错误: {error_summary}", imported_count
        else:
            # 全部成功
            return True, f"全部成功：导入 {imported_count} 名员工", imported_count
    
    @staticmethod
    def import_salary_structures(df: pd.DataFrame, actor: str) -> Tuple[bool, str, int]:
        """Import salary structures from DataFrame."""
        df = ImportService._rename_columns(df, ImportService.SALARY_COLUMNS)
        
        imported_count = 0
        
        with session_scope() as session:
            for idx, row in df.iterrows():
                try:
                    employee_no = str(row.get("employee_no", "")).strip()
                    employee = EmployeeRepository.get_by_employee_no(session, employee_no)
                    if not employee:
                        continue
                    
                    allowances = {}
                    deductions = {}
                    
                    if pd.notna(row.get("allowances_json")):
                        try:
                            allowances = json.loads(str(row.get("allowances_json")))
                        except:
                            pass
                    
                    if pd.notna(row.get("deductions_json")):
                        try:
                            deductions = json.loads(str(row.get("deductions_json")))
                        except:
                            pass
                    
                    SalaryStructureRepository.create_or_update(
                        session,
                        employee_id=employee.id,
                        base_salary=Decimal(str(row.get("base_salary", 0))),
                        hourly_rate=Decimal(str(row.get("hourly_rate", 0))),
                        overtime_multiplier=Decimal(str(row.get("overtime_multiplier", 1.5))),
                        daily_deduction=Decimal(str(row.get("daily_deduction", 0))),
                        allowances=allowances,
                        deductions=deductions,
                    )
                    imported_count += 1
                except Exception as e:
                    continue
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="import_salary_structures",
                result="success",
                metadata={"count": imported_count},
            )
        
        return True, f"成功导入 {imported_count} 条薪资结构", imported_count
    
    @staticmethod
    def import_attendance(df: pd.DataFrame, actor: str) -> Tuple[bool, str, int]:
        """Import attendance data from DataFrame."""
        df = ImportService._rename_columns(df, ImportService.ATTENDANCE_COLUMNS)
        
        imported_count = 0
        
        with session_scope() as session:
            for idx, row in df.iterrows():
                try:
                    employee_no = str(row.get("employee_no", "")).strip()
                    employee = EmployeeRepository.get_by_employee_no(session, employee_no)
                    if not employee:
                        continue
                    
                    period = str(row.get("period", "")).strip()
                    
                    AttendanceRepository.get_or_create(
                        session,
                        employee_id=employee.id,
                        period=period,
                        work_days=int(row.get("work_days", 0)),
                        work_hours=int(row.get("work_days", 0)) * 8,
                        overtime_hours=Decimal(str(row.get("overtime_hours", 0))),
                        absence_days=Decimal(str(row.get("absence_days", 0))),
                    )
                    imported_count += 1
                except Exception as e:
                    continue
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="import_attendance",
                result="success",
                metadata={"count": imported_count},
            )
        
        return True, f"成功导入 {imported_count} 条考勤记录", imported_count
    
    @staticmethod
    def import_adjustments(df: pd.DataFrame, actor: str) -> Tuple[bool, str, int]:
        """Import adjustment data from DataFrame."""
        df = ImportService._rename_columns(df, ImportService.ADJUSTMENT_COLUMNS)
        
        imported_count = 0
        
        with session_scope() as session:
            for idx, row in df.iterrows():
                try:
                    employee_no = str(row.get("employee_no", "")).strip()
                    employee = EmployeeRepository.get_by_employee_no(session, employee_no)
                    if not employee:
                        continue
                    
                    period = str(row.get("period", "")).strip()
                    adj_type_str = str(row.get("type", "")).strip().lower()
                    adj_type = AdjustmentType.ADD if adj_type_str == "add" else AdjustmentType.DEDUCT
                    
                    AdjustmentRepository.create(
                        session,
                        employee_id=employee.id,
                        period=period,
                        adjustment_type=adj_type,
                        amount=Decimal(str(row.get("amount", 0))),
                        reason=str(row.get("reason", "")) if pd.notna(row.get("reason")) else None,
                    )
                    imported_count += 1
                except Exception as e:
                    continue
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="import_adjustments",
                result="success",
                metadata={"count": imported_count},
            )
        
        return True, f"成功导入 {imported_count} 条调整项", imported_count


# =============================================================================
# Export Service
# =============================================================================

class ExportService:
    """
    Report export service.
    报表导出服务
    """
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    @staticmethod
    def export_payroll_summary(
        run_id: int,
        output_path: str,
        actor: str,
        encrypt: bool = False,
        password: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """
        Export payroll summary to Excel.
        
        Args:
            run_id: Payroll run ID
            output_path: Output file path
            actor: Username performing export
            encrypt: Whether to encrypt the file
            password: Password for encryption
            
        Returns:
            Tuple of (success, message, file_path, file_hash)
        """
        from app.security import sanitize_dataframe_for_export
        
        slips = PayrollService.get_payroll_slips(run_id)
        if not slips:
            return False, "没有工资数据", None, None
        
        df = pd.DataFrame(slips)
        
        # Rename columns to Chinese
        column_names = {
            "employee_no": "员工编号",
            "employee_name": "姓名",
            "department": "部门",
            "base_salary": "基本工资",
            "overtime_pay": "加班费",
            "allowances_total": "津贴合计",
            "adjustments_add": "增项调整",
            "gross_salary": "应发工资",
            "absence_deduction": "缺勤扣款",
            "deductions_total": "扣款合计",
            "adjustments_deduct": "扣项调整",
            "tax": "个税",
            "total_deductions": "扣款总计",
            "net_salary": "实发工资",
        }
        df = df.rename(columns=column_names)
        
        # Select and order columns
        export_columns = [
            "员工编号", "姓名", "部门", "基本工资", "加班费", "津贴合计",
            "增项调整", "应发工资", "缺勤扣款", "扣款合计", "扣项调整",
            "个税", "扣款总计", "实发工资"
        ]
        df = df[[col for col in export_columns if col in df.columns]]
        
        # Sanitize for spreadsheet
        df = sanitize_dataframe_for_export(df)
        
        # Export to Excel
        df.to_excel(output_path, index=False, engine="openpyxl")
        
        # Calculate hash
        file_hash = ExportService._calculate_file_hash(output_path)
        
        # Log export
        with session_scope() as session:
            AuditLogRepository.create(
                session,
                actor=actor,
                action="export_payroll_summary",
                result="success",
                resource_type="payroll_run",
                resource_id=run_id,
                metadata={"file_hash": file_hash, "encrypted": encrypt},
            )
        
        return True, "导出成功", output_path, file_hash
    
    @staticmethod
    def export_bank_transfer(
        run_id: int,
        output_path: str,
        actor: str,
        encrypt: bool = False
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """Export bank transfer file with decrypted bank card numbers."""
        from app.security import sanitize_dataframe_for_export
        
        em = get_encryption_manager()
        
        with session_scope() as session:
            slips = PayrollSlipRepository.list_by_run(session, run_id)
            if not slips:
                return False, "没有工资数据", None, None
            
            data = []
            for slip in slips:
                employee = EmployeeRepository.get_by_id(session, slip.employee_id)
                if not employee:
                    continue
                
                bank_card = ""
                if employee.bank_card_encrypted:
                    bank_card = em.decrypt(employee.bank_card_encrypted)
                
                data.append({
                    "员工编号": employee.employee_no,
                    "姓名": employee.name,
                    "银行卡号": bank_card,
                    "实发工资": float(slip.net_salary),
                })
            
            df = pd.DataFrame(data)
            df = sanitize_dataframe_for_export(df)
            df.to_excel(output_path, index=False, engine="openpyxl")
            
            file_hash = ExportService._calculate_file_hash(output_path)
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="export_bank_transfer",
                result="success",
                resource_type="payroll_run",
                resource_id=run_id,
                metadata={"file_hash": file_hash},
            )
        
        return True, "银行转账清单导出成功", output_path, file_hash
    
    @staticmethod
    def export_accounting_voucher(
        run_id: int,
        output_path: str,
        actor: str,
        encrypt: bool = False
    ) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """Export accounting voucher template."""
        from app.security import sanitize_dataframe_for_export
        
        with session_scope() as session:
            run = PayrollRunRepository.get_by_id(session, run_id)
            if not run:
                return False, "工资批次不存在", None, None
            
            # Create accounting entries
            data = [
                {
                    "日期": run.created_at.strftime("%Y-%m-%d"),
                    "摘要": f"{run.period} 工资",
                    "科目": "应付职工薪酬",
                    "借方": float(run.total_gross),
                    "贷方": 0,
                },
                {
                    "日期": run.created_at.strftime("%Y-%m-%d"),
                    "摘要": f"{run.period} 代扣款项",
                    "科目": "其他应付款",
                    "借方": 0,
                    "贷方": float(run.total_deductions),
                },
                {
                    "日期": run.created_at.strftime("%Y-%m-%d"),
                    "摘要": f"{run.period} 实发工资",
                    "科目": "银行存款",
                    "借方": 0,
                    "贷方": float(run.total_net),
                },
            ]
            
            df = pd.DataFrame(data)
            df = sanitize_dataframe_for_export(df)
            df.to_excel(output_path, index=False, engine="openpyxl")
            
            file_hash = ExportService._calculate_file_hash(output_path)
            
            AuditLogRepository.create(
                session,
                actor=actor,
                action="export_accounting_voucher",
                result="success",
                resource_type="payroll_run",
                resource_id=run_id,
                metadata={"file_hash": file_hash},
            )
        
        return True, "会计凭证导出成功", output_path, file_hash


# =============================================================================
# System Service
# =============================================================================

class SystemService:
    """
    System management service.
    系统管理服务
    """
    
    @staticmethod
    def is_initialized() -> bool:
        """Check if system has been initialized (has at least one admin user)."""
        with session_scope() as session:
            count = UserRepository.count(session)
            return count > 0
    
    @staticmethod
    def initialize_system(master_key: str, admin_username: str, admin_password: str) -> Tuple[bool, str]:
        """
        Initialize the system with master key and first admin user.
        
        Args:
            master_key: Master encryption key
            admin_username: Admin username
            admin_password: Admin password
            
        Returns:
            Tuple of (success, message)
        """
        if SystemService.is_initialized():
            return False, "系统已初始化"
        
        # Initialize encryption manager
        from app.security.core import EncryptionManager, _encryption_manager
        global _encryption_manager
        
        # Create encryption manager with master key
        em = EncryptionManager(master_key)
        
        # Create admin user
        success, message = AuthService.create_user(
            admin_username,
            admin_password,
            UserRole.ADMIN,
            actor="system_init"
        )
        
        if success:
            return True, "系统初始化成功"
        else:
            return False, message
    
    @staticmethod
    def get_audit_logs(
        limit: int = 100,
        actor: Optional[str] = None,
        action: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get audit logs."""
        with session_scope() as session:
            logs = AuditLogRepository.list_all(
                session,
                limit=limit,
                actor=actor,
                action=action
            )
            
            return [
                {
                    "id": log.id,
                    "actor": log.actor,
                    "action": log.action,
                    "result": log.result,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "metadata": json.loads(log.metadata_json) if log.metadata_json else None,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ]
    
    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """Get dashboard statistics."""
        with session_scope() as session:
            employee_count = EmployeeRepository.count_active(session)
            user_count = UserRepository.count(session)
            
            runs = PayrollRunRepository.list_all(session, limit=1)
            latest_run = runs[0] if runs else None
            
            return {
                "active_employees": employee_count,
                "total_users": user_count,
                "latest_payroll": {
                    "period": latest_run.period if latest_run else None,
                    "total_net": float(latest_run.total_net) if latest_run else 0,
                    "status": latest_run.status.value if latest_run else None,
                } if latest_run else None,
            }
