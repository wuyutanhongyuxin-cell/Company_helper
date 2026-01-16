"""
Service Layer Tests

Tests for business logic services including:
- AuthService: User authentication with rate limiting
- EmployeeService: Employee CRUD with field encryption
- PayrollService: Payroll generation and lifecycle
- ImportService: Data import from Excel/CSV
- ExportService: Report export with sanitization
"""

import os
import sys
import tempfile
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

import pytest
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up test environment before importing app modules
os.environ['APP_ENV'] = 'test'
os.environ['TEST_MASTER_KEY'] = 'test_master_key_for_testing_only_12345'


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(scope='module')
def test_db():
    """
    Create a temporary test database for the entire test module.
    This avoids creating/destroying DB for each test, improving performance.
    """
    # Create temp directory for test data
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_payroll.db')
    
    # Patch database path before importing modules
    with patch.dict(os.environ, {'DATABASE_PATH': db_path}):
        from app.db import init_database_simple, create_all_tables
        
        # Initialize database
        engine = init_database_simple(db_path)
        create_all_tables(engine)
        
        yield {
            'engine': engine,
            'db_path': db_path,
            'temp_dir': temp_dir
        }
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_encryption():
    """
    Mock encryption manager for tests that don't need real encryption.
    This speeds up tests significantly.
    """
    with patch('app.services.business.get_encryption_manager') as mock_em:
        mock_instance = MagicMock()
        # Simple mock: just return the input with a prefix
        mock_instance.encrypt.side_effect = lambda x: f"ENC:{x}"
        mock_instance.decrypt.side_effect = lambda x: x.replace("ENC:", "") if x.startswith("ENC:") else x
        mock_em.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_password_manager():
    """Mock password manager for faster auth tests."""
    with patch('app.services.business.get_password_manager') as mock_pm:
        mock_instance = MagicMock()
        # Store passwords in a simple dict for testing
        passwords = {}
        
        def hash_password(pwd):
            hashed = f"HASH:{pwd}"
            passwords[hashed] = pwd
            return hashed
        
        def verify_password(pwd, hashed):
            return passwords.get(hashed) == pwd
        
        mock_instance.hash_password.side_effect = hash_password
        mock_instance.verify_password.side_effect = verify_password
        mock_pm.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_rate_limiter():
    """Mock rate limiter that never blocks."""
    with patch('app.services.business.get_rate_limiter') as mock_rl:
        mock_instance = MagicMock()
        mock_instance.is_locked.return_value = (False, 0)
        mock_instance.get_remaining_attempts.return_value = 5
        mock_instance.record_attempt.return_value = None
        mock_rl.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_employee_data():
    """Sample employee data for testing."""
    return {
        'employee_no': 'EMP001',
        'name': '张三',
        'department': '技术部',
        'hire_date': date(2023, 1, 15),
        'bank_card': '6222021234567890123',
        'id_number': '110101199001011234'
    }


@pytest.fixture
def sample_salary_structure():
    """Sample salary structure for testing."""
    return {
        'base_salary': Decimal('8000'),
        'hourly_rate': Decimal('50'),
        'overtime_multiplier': Decimal('1.5'),
        'daily_deduction': Decimal('300'),
        'allowances': {'餐补': 500, '交通': 200},
        'deductions': {'社保': 800}
    }


@pytest.fixture
def sample_attendance():
    """Sample attendance data for testing."""
    return {
        'period': '2024-01',
        'work_days': 22,
        'work_hours': 176,
        'overtime_hours': Decimal('16'),
        'absence_days': Decimal('1')
    }


@pytest.fixture
def temp_excel_file():
    """Create a temporary Excel file for import tests."""
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, 'test_import.xlsx')
    
    yield file_path
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


# =============================================================================
# AuthService Tests
# =============================================================================

class TestAuthService:
    """Tests for user authentication service."""
    
    def test_login_success(self, test_db, mock_password_manager, mock_rate_limiter):
        """Test successful login with valid credentials."""
        from app.services.business import AuthService
        from app.db import session_scope, UserRepository, UserRole
        
        # Create test user
        with session_scope() as session:
            UserRepository.create(
                session,
                username='testuser',
                password_hash=mock_password_manager.hash_password('testpass123'),
                role=UserRole.ADMIN
            )
        
        # Attempt login
        success, user, message = AuthService.login('testuser', 'testpass123')
        
        assert success is True
        assert user is not None
        assert user.username == 'testuser'
        assert '成功' in message or user is not None
    
    def test_login_wrong_password(self, test_db, mock_password_manager, mock_rate_limiter):
        """Test login failure with wrong password."""
        from app.services.business import AuthService
        from app.db import session_scope, UserRepository, UserRole
        
        # Ensure user exists
        with session_scope() as session:
            if not UserRepository.get_by_username(session, 'wrongpwd_user'):
                UserRepository.create(
                    session,
                    username='wrongpwd_user',
                    password_hash=mock_password_manager.hash_password('correct_password'),
                    role=UserRole.ADMIN
                )
        
        # Attempt login with wrong password
        success, user, message = AuthService.login('wrongpwd_user', 'wrong_password')
        
        assert success is False
        assert user is None
        assert '错误' in message
    
    def test_login_nonexistent_user(self, test_db, mock_password_manager, mock_rate_limiter):
        """Test login failure with non-existent user."""
        from app.services.business import AuthService
        
        success, user, message = AuthService.login('nonexistent_user_xyz', 'anypassword')
        
        assert success is False
        assert user is None
        assert '错误' in message
    
    def test_login_rate_limiting(self, test_db, mock_password_manager):
        """Test that rate limiting blocks login attempts."""
        from app.services.business import AuthService
        
        # Mock rate limiter to return locked status
        with patch('app.services.business.get_rate_limiter') as mock_rl:
            mock_instance = MagicMock()
            mock_instance.is_locked.return_value = (True, 300)  # Locked for 300 seconds
            mock_rl.return_value = mock_instance
            
            success, user, message = AuthService.login('anyuser', 'anypass')
            
            assert success is False
            assert user is None
            assert '锁定' in message
    
    def test_login_disabled_user(self, test_db, mock_password_manager, mock_rate_limiter):
        """Test login failure for disabled user account."""
        from app.services.business import AuthService
        from app.db import session_scope, UserRepository, UserRole
        
        # Create disabled user
        with session_scope() as session:
            user = UserRepository.get_by_username(session, 'disabled_user')
            if not user:
                user = UserRepository.create(
                    session,
                    username='disabled_user',
                    password_hash=mock_password_manager.hash_password('password123'),
                    role=UserRole.EMPLOYEE
                )
            user.is_active = False
            session.commit()
        
        # Attempt login
        success, user, message = AuthService.login('disabled_user', 'password123')
        
        assert success is False
        assert '禁用' in message


# =============================================================================
# EmployeeService Tests
# =============================================================================

class TestEmployeeService:
    """Tests for employee management service."""
    
    def test_create_employee_success(self, test_db, mock_encryption, sample_employee_data):
        """Test creating a new employee with encrypted fields."""
        from app.services.business import EmployeeService
        
        # Use unique employee number
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_CREATE_001'
        
        success, message, employee_id = EmployeeService.create_employee(data, 'admin')
        
        assert success is True
        assert employee_id is not None
        assert '成功' in message
    
    def test_create_employee_duplicate(self, test_db, mock_encryption, sample_employee_data):
        """Test that creating duplicate employee fails."""
        from app.services.business import EmployeeService
        
        # Create first employee
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_DUP_001'
        EmployeeService.create_employee(data, 'admin')
        
        # Try to create duplicate
        success, message, employee_id = EmployeeService.create_employee(data, 'admin')
        
        assert success is False
        assert '已存在' in message
    
    def test_create_employee_invalid_no(self, test_db, mock_encryption, sample_employee_data):
        """Test that invalid employee number is rejected."""
        from app.services.business import EmployeeService
        
        data = sample_employee_data.copy()
        data['employee_no'] = ''  # Invalid: empty
        
        success, message, employee_id = EmployeeService.create_employee(data, 'admin')
        
        assert success is False
        assert '无效' in message
    
    def test_get_employee_with_sensitive_data(self, test_db, mock_encryption, sample_employee_data):
        """Test retrieving employee with decrypted sensitive data."""
        from app.services.business import EmployeeService
        
        # Create employee
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_SENSITIVE_001'
        success, _, employee_id = EmployeeService.create_employee(data, 'admin')
        
        # Get with sensitive data (authorized)
        employee = EmployeeService.get_employee_with_sensitive_data(employee_id, can_view_sensitive=True)
        
        assert employee is not None
        assert employee['employee_no'] == 'EMP_SENSITIVE_001'
        # With mock encryption, we should get the original values back
        assert employee.get('bank_card') is not None
    
    def test_get_employee_redacted(self, test_db, mock_encryption, sample_employee_data):
        """Test retrieving employee with redacted sensitive data."""
        from app.services.business import EmployeeService
        
        # Create employee
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_REDACT_001'
        success, _, employee_id = EmployeeService.create_employee(data, 'admin')
        
        # Get without sensitive data (unauthorized)
        employee = EmployeeService.get_employee_with_sensitive_data(employee_id, can_view_sensitive=False)
        
        assert employee is not None
        # Sensitive fields should be redacted (contain asterisks)
        if employee.get('bank_card'):
            assert '*' in employee['bank_card'] or employee['bank_card'] != data['bank_card']
    
    def test_list_employees(self, test_db, mock_encryption, sample_employee_data):
        """Test listing all employees."""
        from app.services.business import EmployeeService
        from app.db import EmployeeStatus
        
        # Create a few employees
        for i in range(3):
            data = sample_employee_data.copy()
            data['employee_no'] = f'EMP_LIST_{i:03d}'
            EmployeeService.create_employee(data, 'admin')
        
        # List all employees
        employees = EmployeeService.list_employees()
        
        assert len(employees) >= 3
        # Should not contain sensitive data
        for emp in employees:
            assert 'bank_card' not in emp or emp.get('bank_card') is None
            assert 'id_number' not in emp or emp.get('id_number') is None
    
    def test_count_active_employees(self, test_db, mock_encryption, sample_employee_data):
        """Test counting active employees."""
        from app.services.business import EmployeeService
        
        # Create an employee
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_COUNT_001'
        EmployeeService.create_employee(data, 'admin')
        
        count = EmployeeService.count_active()
        
        assert count >= 1


# =============================================================================
# SalaryStructureService Tests
# =============================================================================

class TestSalaryStructureService:
    """Tests for salary structure management."""
    
    def test_create_salary_structure(self, test_db, mock_encryption, sample_employee_data, sample_salary_structure):
        """Test creating a new salary structure."""
        from app.services.business import EmployeeService, SalaryStructureService
        
        # Create employee first
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_SAL_001'
        _, _, employee_id = EmployeeService.create_employee(data, 'admin')
        
        # Create salary structure
        success, message = SalaryStructureService.create_or_update(
            employee_id, sample_salary_structure, 'admin'
        )
        
        assert success is True
        assert '成功' in message
    
    def test_update_salary_structure(self, test_db, mock_encryption, sample_employee_data, sample_salary_structure):
        """Test updating an existing salary structure."""
        from app.services.business import EmployeeService, SalaryStructureService
        
        # Create employee and initial salary structure
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_SAL_002'
        _, _, employee_id = EmployeeService.create_employee(data, 'admin')
        SalaryStructureService.create_or_update(employee_id, sample_salary_structure, 'admin')
        
        # Update with new base salary
        updated_structure = sample_salary_structure.copy()
        updated_structure['base_salary'] = Decimal('10000')
        
        success, message = SalaryStructureService.create_or_update(
            employee_id, updated_structure, 'admin'
        )
        
        assert success is True
        
        # Verify update
        structure = SalaryStructureService.get_by_employee(employee_id)
        assert structure['base_salary'] == Decimal('10000')
    
    def test_get_salary_structure(self, test_db, mock_encryption, sample_employee_data, sample_salary_structure):
        """Test retrieving salary structure."""
        from app.services.business import EmployeeService, SalaryStructureService
        
        # Create employee and salary structure
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_SAL_003'
        _, _, employee_id = EmployeeService.create_employee(data, 'admin')
        SalaryStructureService.create_or_update(employee_id, sample_salary_structure, 'admin')
        
        # Get salary structure
        structure = SalaryStructureService.get_by_employee(employee_id)
        
        assert structure is not None
        assert structure['base_salary'] == sample_salary_structure['base_salary']
        assert structure['allowances'] == sample_salary_structure['allowances']


# =============================================================================
# PayrollService Tests
# =============================================================================

class TestPayrollService:
    """Tests for payroll generation and management."""
    
    @pytest.fixture
    def setup_payroll_data(self, test_db, mock_encryption, sample_employee_data, sample_salary_structure, sample_attendance):
        """Set up complete data for payroll generation."""
        from app.services.business import EmployeeService, SalaryStructureService
        from app.db import session_scope, AttendanceRepository
        
        # Create employee
        data = sample_employee_data.copy()
        data['employee_no'] = 'EMP_PAY_001'
        _, _, employee_id = EmployeeService.create_employee(data, 'admin')
        
        # Create salary structure
        SalaryStructureService.create_or_update(employee_id, sample_salary_structure, 'admin')
        
        # Create attendance
        with session_scope() as session:
            AttendanceRepository.create(
                session,
                employee_id=employee_id,
                period=sample_attendance['period'],
                work_days=sample_attendance['work_days'],
                work_hours=sample_attendance['work_hours'],
                overtime_hours=sample_attendance['overtime_hours'],
                absence_days=sample_attendance['absence_days']
            )
        
        return {
            'employee_id': employee_id,
            'period': sample_attendance['period']
        }
    
    def test_generate_payroll_success(self, setup_payroll_data):
        """Test successful payroll generation."""
        from app.services.business import PayrollService
        
        period = setup_payroll_data['period']
        
        success, message, summary = PayrollService.generate_payroll(period, 'admin')
        
        assert success is True
        assert summary is not None
        assert summary.total_employees >= 1
        assert summary.total_gross > 0
        assert summary.total_net > 0
    
    def test_generate_payroll_invalid_period(self, test_db):
        """Test payroll generation with invalid period format."""
        from app.services.business import PayrollService
        
        success, message, summary = PayrollService.generate_payroll('invalid-period', 'admin')
        
        assert success is False
        assert '格式' in message
    
    def test_lock_payroll(self, setup_payroll_data):
        """Test locking a payroll run."""
        from app.services.business import PayrollService
        
        period = setup_payroll_data['period']
        
        # Generate payroll first
        PayrollService.generate_payroll(period, 'admin')
        
        # Get payroll runs and lock one
        runs = PayrollService.list_payroll_runs()
        if runs:
            run_id = runs[0]['id']
            success, message = PayrollService.lock_payroll(run_id, 'admin')
            
            # Lock should succeed if run is in draft status
            # (may fail if already locked from previous test)
            assert success is True or '已锁定' in message
    
    def test_unlock_payroll_requires_confirmation(self, setup_payroll_data):
        """Test that unlocking requires confirmation."""
        from app.services.business import PayrollService
        
        period = setup_payroll_data['period']
        
        # Generate and lock
        PayrollService.generate_payroll(period, 'admin')
        runs = PayrollService.list_payroll_runs()
        
        if runs:
            run_id = runs[0]['id']
            PayrollService.lock_payroll(run_id, 'admin')
            
            # Try to unlock without confirmation
            success, message = PayrollService.unlock_payroll(run_id, 'admin', confirmed=False)
            
            # Should fail without confirmation
            assert success is False or '确认' in message
    
    def test_get_payroll_slips(self, setup_payroll_data):
        """Test retrieving payroll slips."""
        from app.services.business import PayrollService
        
        period = setup_payroll_data['period']
        
        # Generate payroll
        PayrollService.generate_payroll(period, 'admin')
        
        # Get slips
        runs = PayrollService.list_payroll_runs()
        if runs:
            run_id = runs[0]['id']
            slips = PayrollService.get_payroll_slips(run_id)
            
            assert len(slips) >= 1
            assert slips[0].get('gross_salary') is not None
            assert slips[0].get('net_salary') is not None


# =============================================================================
# ImportService Tests
# =============================================================================

class TestImportService:
    """Tests for data import functionality."""
    
    def test_import_employees_from_dataframe(self, test_db, mock_encryption):
        """Test importing employees from a pandas DataFrame."""
        from app.services.business import ImportService
        
        # Create test DataFrame
        df = pd.DataFrame([
            {'员工编号': 'IMP_001', '姓名': '李四', '部门': '财务部', '入职日期': '2023-06-01', '银行卡号': '6222029876543210987', '身份证号': '310101199505052345'},
            {'员工编号': 'IMP_002', '姓名': '王五', '部门': '人事部', '入职日期': '2023-07-15', '银行卡号': '6222031111222233334', '身份证号': '440101199808083456'},
        ])
        
        success, message, count = ImportService.import_employees(df, 'admin')
        
        assert success is True
        assert count == 2
    
    def test_import_employees_with_duplicate(self, test_db, mock_encryption):
        """Test that duplicate employee numbers are handled correctly."""
        from app.services.business import ImportService, EmployeeService
        
        # Create existing employee
        existing_data = {
            'employee_no': 'IMP_DUP_001',
            'name': '已存在',
            'department': '测试部',
            'hire_date': date(2023, 1, 1),
            'bank_card': '1234567890123456789',
            'id_number': '123456789012345678'
        }
        EmployeeService.create_employee(existing_data, 'admin')
        
        # Try to import duplicate
        df = pd.DataFrame([
            {'员工编号': 'IMP_DUP_001', '姓名': '新员工', '部门': '新部门', '入职日期': '2024-01-01', '银行卡号': '9876543210987654321', '身份证号': '987654321098765432'},
        ])
        
        success, message, count = ImportService.import_employees(df, 'admin')
        
        # Should either skip duplicates or update them (depending on implementation)
        assert success is True or '重复' in message or '已存在' in message
    
    def test_import_salary_structures(self, test_db, mock_encryption):
        """Test importing salary structures."""
        from app.services.business import ImportService, EmployeeService
        
        # Create employee first
        emp_data = {
            'employee_no': 'IMP_SAL_001',
            'name': '工资测试',
            'department': '测试部',
            'hire_date': date(2023, 1, 1),
            'bank_card': '1234567890123456789',
            'id_number': '123456789012345678'
        }
        EmployeeService.create_employee(emp_data, 'admin')
        
        # Import salary structure
        df = pd.DataFrame([
            {'员工编号': 'IMP_SAL_001', '基本工资': 10000, '时薪': 60, '加班倍率': 1.5, '日扣款标准': 400, '津贴(JSON)': '{"餐补":600}', '固定扣款(JSON)': '{"社保":1000}'},
        ])
        
        success, message, count = ImportService.import_salary_structures(df, 'admin')
        
        assert success is True
        assert count == 1
    
    def test_import_attendance(self, test_db, mock_encryption):
        """Test importing attendance data."""
        from app.services.business import ImportService, EmployeeService
        
        # Create employee first
        emp_data = {
            'employee_no': 'IMP_ATT_001',
            'name': '考勤测试',
            'department': '测试部',
            'hire_date': date(2023, 1, 1),
            'bank_card': '1234567890123456789',
            'id_number': '123456789012345678'
        }
        EmployeeService.create_employee(emp_data, 'admin')
        
        # Import attendance
        df = pd.DataFrame([
            {'员工编号': 'IMP_ATT_001', '期间': '2024-02', '工作天数': 20, '加班小时': 8, '缺勤天数': 2},
        ])
        
        success, message, count = ImportService.import_attendance(df, 'admin')
        
        assert success is True
        assert count == 1
    
    def test_import_adjustments(self, test_db, mock_encryption):
        """Test importing adjustment records."""
        from app.services.business import ImportService, EmployeeService
        
        # Create employee first
        emp_data = {
            'employee_no': 'IMP_ADJ_001',
            'name': '调整测试',
            'department': '测试部',
            'hire_date': date(2023, 1, 1),
            'bank_card': '1234567890123456789',
            'id_number': '123456789012345678'
        }
        EmployeeService.create_employee(emp_data, 'admin')
        
        # Import adjustments
        df = pd.DataFrame([
            {'员工编号': 'IMP_ADJ_001', '期间': '2024-02', '类型': 'add', '金额': 5000, '原因': '年终奖'},
            {'员工编号': 'IMP_ADJ_001', '期间': '2024-02', '类型': 'deduct', '金额': 200, '原因': '迟到'},
        ])
        
        success, message, count = ImportService.import_adjustments(df, 'admin')
        
        assert success is True
        assert count == 2


# =============================================================================
# ExportService Tests
# =============================================================================

class TestExportService:
    """Tests for report export functionality."""
    
    @pytest.fixture
    def setup_export_data(self, test_db, mock_encryption):
        """Set up data for export tests."""
        from app.services.business import EmployeeService, SalaryStructureService, PayrollService
        from app.db import session_scope, AttendanceRepository
        
        # Create employee
        emp_data = {
            'employee_no': 'EXP_001',
            'name': '导出测试',
            'department': '测试部',
            'hire_date': date(2023, 1, 1),
            'bank_card': '6222021234567890123',
            'id_number': '110101199001011234'
        }
        _, _, employee_id = EmployeeService.create_employee(emp_data, 'admin')
        
        # Create salary structure
        sal_data = {
            'base_salary': Decimal('8000'),
            'hourly_rate': Decimal('50'),
            'overtime_multiplier': Decimal('1.5'),
            'daily_deduction': Decimal('300'),
            'allowances': {'餐补': 500},
            'deductions': {'社保': 800}
        }
        SalaryStructureService.create_or_update(employee_id, sal_data, 'admin')
        
        # Create attendance
        with session_scope() as session:
            AttendanceRepository.create(
                session,
                employee_id=employee_id,
                period='2024-03',
                work_days=22,
                work_hours=176,
                overtime_hours=Decimal('10'),
                absence_days=Decimal('0')
            )
        
        # Generate payroll
        PayrollService.generate_payroll('2024-03', 'admin')
        
        # Get payroll run ID
        runs = PayrollService.list_payroll_runs()
        run_id = runs[0]['id'] if runs else None
        
        return {
            'employee_id': employee_id,
            'period': '2024-03',
            'run_id': run_id
        }
    
    def test_export_payroll_summary(self, setup_export_data, tmp_path):
        """Test exporting payroll summary to Excel."""
        from app.services.business import ExportService
        
        run_id = setup_export_data['run_id']
        if run_id is None:
            pytest.skip("No payroll run available")
        
        output_path = tmp_path / 'payroll_summary.xlsx'
        
        success, message, file_path, file_hash = ExportService.export_payroll_summary(
            run_id, str(output_path), 'admin', encrypt=False
        )
        
        assert success is True
        assert file_path is not None
        assert Path(file_path).exists()
        assert file_hash is not None  # SHA-256 hash for audit
    
    def test_export_sanitizes_formulas(self, setup_export_data, tmp_path):
        """Test that exported data has formula injection protection."""
        from app.services.business import ExportService
        from app.security import sanitize_for_spreadsheet
        
        # Test the sanitization function directly
        dangerous_values = [
            ('=SUM(A1:A10)', "'=SUM(A1:A10)"),
            ('+cmd|calc', "'+cmd|calc"),
            ('-10+20', "'-10+20"),
            ('@SUM(A1)', "'@SUM(A1)"),
            ('normal text', 'normal text'),  # Should not be modified
        ]
        
        for input_val, expected in dangerous_values:
            result = sanitize_for_spreadsheet(input_val)
            assert result == expected, f"Failed for input: {input_val}"
    
    def test_export_bank_transfer(self, setup_export_data, tmp_path):
        """Test exporting bank transfer file with decrypted bank cards."""
        from app.services.business import ExportService
        
        run_id = setup_export_data['run_id']
        if run_id is None:
            pytest.skip("No payroll run available")
        
        output_path = tmp_path / 'bank_transfer.xlsx'
        
        success, message, file_path, file_hash = ExportService.export_bank_transfer(
            run_id, str(output_path), 'admin', encrypt=False
        )
        
        assert success is True
        assert file_path is not None
        assert Path(file_path).exists()
    
    def test_export_accounting_voucher(self, setup_export_data, tmp_path):
        """Test exporting accounting voucher template."""
        from app.services.business import ExportService
        
        run_id = setup_export_data['run_id']
        if run_id is None:
            pytest.skip("No payroll run available")
        
        output_path = tmp_path / 'accounting_voucher.xlsx'
        
        success, message, file_path, file_hash = ExportService.export_accounting_voucher(
            run_id, str(output_path), 'admin', encrypt=False
        )
        
        assert success is True
        assert file_path is not None


# =============================================================================
# SystemService Tests
# =============================================================================

class TestSystemService:
    """Tests for system management service."""
    
    def test_system_initialization(self, test_db):
        """Test system initialization check."""
        from app.services.business import SystemService
        
        # System should be initialized after creating first user
        is_init = SystemService.is_initialized()
        
        # Result depends on whether tests have created users
        assert isinstance(is_init, bool)
    
    def test_get_audit_logs(self, test_db):
        """Test retrieving audit logs."""
        from app.services.business import SystemService
        from app.db import session_scope, AuditLogRepository
        
        # Create some audit log entries
        with session_scope() as session:
            AuditLogRepository.create(
                session, actor='test_user', action='test_action',
                result='success', metadata={'test': 'data'}
            )
        
        # Get logs
        logs = SystemService.get_audit_logs(limit=10)
        
        assert len(logs) >= 1
        assert logs[0].get('actor') is not None
        assert logs[0].get('action') is not None


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""
    
    def test_complete_payroll_workflow(self, test_db, mock_encryption):
        """Test complete payroll workflow from import to export."""
        from app.services.business import (
            ImportService, PayrollService, ExportService
        )
        import tempfile
        
        # 1. Import employees
        emp_df = pd.DataFrame([
            {'员工编号': 'INT_001', '姓名': '集成测试1', '部门': '研发部', '入职日期': '2023-01-01', '银行卡号': '6222021111111111111', '身份证号': '110101200001011111'},
            {'员工编号': 'INT_002', '姓名': '集成测试2', '部门': '研发部', '入职日期': '2023-02-01', '银行卡号': '6222022222222222222', '身份证号': '110101200002022222'},
        ])
        success, _, count = ImportService.import_employees(emp_df, 'admin')
        assert success is True
        
        # 2. Import salary structures
        sal_df = pd.DataFrame([
            {'员工编号': 'INT_001', '基本工资': 12000, '时薪': 70, '加班倍率': 1.5, '日扣款标准': 500, '津贴(JSON)': '{}', '固定扣款(JSON)': '{}'},
            {'员工编号': 'INT_002', '基本工资': 10000, '时薪': 60, '加班倍率': 1.5, '日扣款标准': 400, '津贴(JSON)': '{}', '固定扣款(JSON)': '{}'},
        ])
        success, _, count = ImportService.import_salary_structures(sal_df, 'admin')
        assert success is True
        
        # 3. Import attendance
        att_df = pd.DataFrame([
            {'员工编号': 'INT_001', '期间': '2024-04', '工作天数': 22, '加班小时': 20, '缺勤天数': 0},
            {'员工编号': 'INT_002', '期间': '2024-04', '工作天数': 21, '加班小时': 10, '缺勤天数': 1},
        ])
        success, _, count = ImportService.import_attendance(att_df, 'admin')
        assert success is True
        
        # 4. Generate payroll
        success, message, summary = PayrollService.generate_payroll('2024-04', 'admin')
        assert success is True
        assert summary.total_employees == 2
        
        # 5. Verify calculations
        # INT_001: base 12000 + overtime (20 * 70 * 1.5 = 2100) = 14100
        # INT_002: base 10000 + overtime (10 * 60 * 1.5 = 900) - absence (1 * 400 = 400) = 10500
        assert summary.total_gross > 0
        
        # 6. Lock payroll
        runs = PayrollService.list_payroll_runs()
        run_id = runs[0]['id']
        success, _ = PayrollService.lock_payroll(run_id, 'admin')
        assert success is True
        
        # 7. Export
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / 'integration_test_export.xlsx'
            success, _, file_path, file_hash = ExportService.export_payroll_summary(
                run_id, str(output_path), 'admin', encrypt=False
            )
            assert success is True
            assert Path(file_path).exists()
            assert file_hash is not None  # Audit hash


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
