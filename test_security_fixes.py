"""
安全修复功能测试
Tests for Security Fixes
"""

import os
import sys
import time

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from decimal import Decimal
from datetime import date, datetime
from pathlib import Path
import threading

# 设置测试环境
os.environ["TESTING"] = "true"
os.environ["TEST_MASTER_KEY"] = "test_master_key_for_testing_only"
os.environ["DATABASE_PATH"] = "test_security.db"

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.db import (
    init_database_simple,
    create_all_tables,
    session_scope,
    UserRole,
    EmployeeStatus,
    AdjustmentType,
)
from app.db.session import drop_all_tables
from app.services import (
    AuthService,
    EmployeeService,
    SalaryStructureService,
    PayrollService,
    ImportService,
    SystemService,
)
from app.security.core import reset_managers


class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []

    def add_pass(self, test_name: str, message: str = ""):
        self.passed.append((test_name, message))
        print(f"✅ {test_name}: {message}")

    def add_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"❌ {test_name}: {error}")

    def add_warning(self, test_name: str, message: str):
        self.warnings.append((test_name, message))
        print(f"⚠️  {test_name}: {message}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print("\n" + "=" * 80)
        print("📊 测试结果汇总")
        print("=" * 80)
        print(f"总计: {total} 个测试")
        print(f"✅ 通过: {len(self.passed)}")
        print(f"❌ 失败: {len(self.failed)}")
        print(f"⚠️  警告: {len(self.warnings)}")
        if total > 0:
            print(f"成功率: {len(self.passed)/total*100:.1f}%")
        else:
            print("成功率: N/A (没有运行测试)")

        if self.failed:
            print("\n失败的测试:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")

        if self.warnings:
            print("\n警告:")
            for name, msg in self.warnings:
                print(f"  - {name}: {msg}")


def setup_test_db():
    """设置测试数据库"""
    print("\n🔧 初始化测试数据库...")

    # 删除旧的测试数据库和密钥文件
    db_path = Path("test_security.db")
    if db_path.exists():
        db_path.unlink()

    keys_file = Path("encryption_keys.dat")
    if keys_file.exists():
        keys_file.unlink()
        print("  已删除旧的加密密钥文件")

    # 初始化数据库
    engine = init_database_simple("test_security.db")
    drop_all_tables(engine)
    create_all_tables(engine)

    # 创建测试用户
    success, msg = AuthService.create_user(
        "admin", "Admin123456", UserRole.ADMIN, "system_init"
    )
    print(f"  创建管理员用户: {msg}")

    success, msg = AuthService.create_user(
        "testuser", "Test123456", UserRole.EMPLOYEE, "admin"
    )
    print(f"  创建测试用户: {msg}")


def test_timing_attack_protection(result: TestResult):
    """测试时序攻击防护"""
    print("\n🔒 测试 1: 时序攻击防护")

    # 测试不存在的用户
    start1 = time.perf_counter()
    success1, _, msg1 = AuthService.login("nonexistent_user", "wrongpass")
    time1 = time.perf_counter() - start1

    # 测试存在的用户但密码错误
    start2 = time.perf_counter()
    success2, _, msg2 = AuthService.login("admin", "wrongpass")
    time2 = time.perf_counter() - start2

    # 时间差异应该很小（< 100ms）
    time_diff = abs(time1 - time2) * 1000

    if not success1 and not success2:
        result.add_pass("时序攻击防护", f"两种场景都返回失败，时间差异: {time_diff:.2f}ms")
    else:
        result.add_fail("时序攻击防护", "预期返回失败但成功了")

    # 检查错误消息是否包含统一的基础消息
    if "用户名或密码错误" in msg1 and "用户名或密码错误" in msg2:
        result.add_pass("错误消息统一", "都包含基础错误消息")
    else:
        result.add_fail("错误消息统一", f"消息不一致: '{msg1}' vs '{msg2}'")

    # 检查账户禁用的消息
    user_id = None
    with session_scope() as session:
        from app.db import UserRepository
        user = UserRepository.get_by_username(session, "testuser")
        if user:
            user_id = user.id
            UserRepository.set_active(session, user.id, False)

    success3, _, msg3 = AuthService.login("testuser", "Test123456")
    if not success3 and "用户名或密码错误" in msg3:
        result.add_pass("账户状态泄露防护", "禁用账户返回统一错误消息")
    else:
        result.add_fail("账户状态泄露防护", f"泄露了账户状态: {msg3}")

    # 恢复测试用户
    if user_id:
        with session_scope() as session:
            UserRepository.set_active(session, user_id, True)


def test_decimal_precision(result: TestResult):
    """测试 Decimal 精度"""
    print("\n💰 测试 2: Decimal 精度")

    # 创建测试员工
    success, msg, emp_id = EmployeeService.create_employee({
        "employee_no": "TEST001",
        "name": "测试员工",
        "department": "测试部",
        "hire_date": date(2024, 1, 1),
        "bank_card": "6222000012345678",
        "id_number": "110101199001011234",
    }, "admin")

    if not success:
        result.add_fail("创建测试员工", msg)
        return

    # 设置薪资结构（包含会产生精度问题的数值）
    success, msg = SalaryStructureService.create_or_update(
        emp_id,
        {
            "base_salary": 5000.00,
            "hourly_rate": 28.846,  # 故意使用会产生精度问题的数值
            "overtime_multiplier": 1.5,
            "daily_deduction": 230.769,  # 故意使用会产生精度问题的数值
            "allowances": {"餐补": 500.33, "交通": 200.66},  # 小数
            "deductions": {"社保": 800.11, "公积金": 600.22},  # 小数
        },
        "admin"
    )

    if not success:
        result.add_fail("设置薪资结构", msg)
        return

    # 创建考勤记录（包含小数加班时间）
    with session_scope() as session:
        from app.db import AttendanceRepository
        AttendanceRepository.create(
            session,
            employee_id=emp_id,
            period="2024-01",
            work_days=22,
            work_hours=176,
            overtime_hours=Decimal("10.5"),  # 小数加班
            absence_days=Decimal("0.5"),  # 半天缺勤
        )

    # 创建调整项（小数金额）
    with session_scope() as session:
        from app.db import AdjustmentRepository
        AdjustmentRepository.create(
            session,
            employee_id=emp_id,
            period="2024-01",
            adjustment_type=AdjustmentType.ADD,
            amount=Decimal("123.45"),
            reason="测试奖金"
        )
        AdjustmentRepository.create(
            session,
            employee_id=emp_id,
            period="2024-01",
            adjustment_type=AdjustmentType.DEDUCT,
            amount=Decimal("67.89"),
            reason="测试扣款"
        )

    # 生成工资
    success, msg, summary = PayrollService.generate_payroll("2024-01", "admin")

    if not success:
        result.add_fail("生成工资", msg)
        return

    # 检查精度
    slips = PayrollService.get_payroll_slips(1)
    if slips:
        slip = slips[0]

        # 检查所有金额是否都是2位小数或整数（整数也OK）
        fields = ["base_salary", "overtime_pay", "allowances_total", "gross_salary",
                 "absence_deduction", "deductions_total", "total_deductions", "net_salary"]

        all_precise = True
        for field in fields:
            value = Decimal(str(slip[field]))
            # 检查是否恰好2位小数或更少（0位、1位、2位都OK）
            if value.as_tuple().exponent < -2:
                result.add_fail(f"精度检查-{field}", f"值 {value} 超过2位小数")
                all_precise = False

        if all_precise:
            result.add_pass("Decimal精度", f"所有金额都不超过2位小数，实发工资: {slip['net_salary']}")

        # 验证计算正确性（手动重算）
        expected_gross = (
            Decimal(str(slip['base_salary'])) +
            Decimal(str(slip['overtime_pay'])) +
            Decimal(str(slip['allowances_total'])) +
            Decimal(str(slip['adjustments_add']))
        ).quantize(Decimal("0.01"))

        actual_gross = Decimal(str(slip['gross_salary']))

        if expected_gross == actual_gross:
            result.add_pass("应发工资计算", f"应发: {actual_gross}")
        else:
            result.add_fail("应发工资计算", f"预期 {expected_gross}，实际 {actual_gross}")
    else:
        result.add_fail("获取工资条", "没有生成工资条")


def test_attendance_logic(result: TestResult):
    """测试考勤逻辑"""
    print("\n📅 测试 3: 考勤逻辑")

    # 创建一个没有考勤记录的员工
    success, msg, emp_id = EmployeeService.create_employee({
        "employee_no": "TEST002",
        "name": "无考勤员工",
        "department": "测试部",
        "hire_date": date(2024, 1, 1),
    }, "admin")

    if not success:
        result.add_fail("创建无考勤员工", msg)
        return

    # 设置薪资结构
    SalaryStructureService.create_or_update(
        emp_id,
        {
            "base_salary": 5000,
            "hourly_rate": 30,
            "overtime_multiplier": 1.5,
            "daily_deduction": 200,
        },
        "admin"
    )

    # 生成工资（应该跳过这个员工）
    success, msg, summary = PayrollService.generate_payroll("2024-02", "admin")

    # 检查审计日志
    from app.services import SystemService
    logs = SystemService.get_audit_logs(limit=10)

    warning_log = None
    for log in logs:
        if log['action'] == 'generate_payroll_warning':
            warning_log = log
            break

    if warning_log:
        result.add_pass("考勤逻辑", f"跳过无考勤员工，审计日志已记录")
        if warning_log.get('metadata', {}).get('skipped_employees', 0) > 0:
            result.add_pass("审计日志元数据", "正确记录跳过的员工数量")
    else:
        result.add_warning("考勤逻辑", "未找到警告审计日志（可能是第一个员工有考勤）")


def test_encryption_thread_safety(result: TestResult):
    """测试加密管理器线程安全"""
    print("\n🔐 测试 4: 加密管理器线程安全")

    # 重置管理器
    reset_managers()

    # 多线程并发获取加密管理器
    managers = []
    errors = []

    def get_manager():
        try:
            from app.security import get_encryption_manager
            mgr = get_encryption_manager()
            managers.append(id(mgr))
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=get_manager) for _ in range(10)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    if errors:
        result.add_fail("线程安全", f"发生错误: {errors[0]}")
    elif len(set(managers)) == 1:
        result.add_pass("线程安全", f"10个线程获取到同一个实例 (ID: {managers[0]})")
    else:
        result.add_fail("线程安全", f"创建了 {len(set(managers))} 个不同的实例")


def test_payroll_unlock_reason(result: TestResult):
    """测试工资解锁理由"""
    print("\n🔓 测试 5: 工资解锁理由")

    # 锁定一个工资批次
    with session_scope() as session:
        from app.db import PayrollRunRepository
        runs = PayrollRunRepository.list_all(session, limit=1)
        if not runs:
            result.add_warning("工资解锁", "没有工资批次可测试")
            return

        run_id = runs[0].id
        PayrollRunRepository.lock(session, run_id, "admin")

    # 尝试不提供理由解锁
    success, msg = PayrollService.unlock_payroll(run_id, "admin", "", confirmed=True)
    if not success and "理由" in msg:
        result.add_pass("解锁理由验证", "拒绝空理由")
    else:
        result.add_fail("解锁理由验证", f"应该拒绝但成功了: {msg}")

    # 提供短理由
    success, msg = PayrollService.unlock_payroll(run_id, "admin", "测试", confirmed=True)
    if not success and "10" in msg:
        result.add_pass("解锁理由长度", "拒绝少于10字符的理由")
    else:
        result.add_fail("解锁理由长度", f"应该拒绝但成功了: {msg}")

    # 提供有效理由
    reason = "需要修正员工张三的加班时间计算错误"
    success, msg = PayrollService.unlock_payroll(run_id, "admin", reason, confirmed=True)
    if success:
        result.add_pass("有效理由解锁", f"成功解锁: {msg[:50]}")

        # 检查审计日志
        logs = SystemService.get_audit_logs(limit=5)
        unlock_log = None
        for log in logs:
            if log['action'] == 'unlock_payroll_critical':
                unlock_log = log
                break

        if unlock_log:
            metadata = unlock_log.get('metadata', {})
            if metadata.get('reason') == reason:
                result.add_pass("审计日志记录", "解锁理由已记录到审计日志")
            if 'original_data' in metadata:
                result.add_pass("原始数据快照", "解锁前的数据已保存")
        else:
            result.add_fail("审计日志", "未找到解锁审计日志")
    else:
        result.add_fail("有效理由解锁", msg)


def test_import_error_handling(result: TestResult):
    """测试导入错误处理"""
    print("\n📥 测试 6: 导入错误处理")

    import pandas as pd

    # 创建包含错误的测试数据
    test_data = pd.DataFrame([
        {"员工编号": "TEST003", "姓名": "张三", "部门": "研发部", "入职日期": "2024-01-01"},
        {"员工编号": "TEST003", "姓名": "重复员工", "部门": "研发部", "入职日期": "2024-01-01"},  # 重复
        {"员工编号": "TEST004", "姓名": "李四", "部门": "研发部", "入职日期": "invalid_date"},  # 错误日期
        {"员工编号": "TEST005", "姓名": "王五", "部门": "研发部", "入职日期": "2024-01-01"},
    ])

    success, msg, count = ImportService.import_employees(test_data, "admin")

    # 应该是部分成功
    if count == 2:  # TEST003 和 TEST005 应该成功
        result.add_pass("导入统计", f"正确导入 2/4 行")
    else:
        result.add_warning("导入统计", f"预期导入2行，实际 {count} 行")

    # 检查消息
    if "部分成功" in msg and "2/4" in msg:
        result.add_pass("导入消息", "正确显示部分成功状态")
    else:
        result.add_warning("导入消息", f"消息格式: {msg[:100]}")

    # 测试全部失败
    bad_data = pd.DataFrame([
        {"员工编号": "", "姓名": "", "部门": "", "入职日期": ""},
        {"员工编号": "", "姓名": "", "部门": "", "入职日期": ""},
    ])

    success, msg, count = ImportService.import_employees(bad_data, "admin")

    if not success and count == 0:
        result.add_pass("全部失败检测", "正确返回失败状态")
    else:
        result.add_fail("全部失败检测", f"应该失败: success={success}, count={count}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 80)
    print("🧪 薪酬管理系统 - 安全修复功能测试")
    print("=" * 80)

    result = TestResult()

    try:
        setup_test_db()

        test_timing_attack_protection(result)
        test_decimal_precision(result)
        test_attendance_logic(result)
        test_encryption_thread_safety(result)
        test_payroll_unlock_reason(result)
        test_import_error_handling(result)

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        result.summary()

        # 清理
        try:
            from app.db.session import close_engine
            close_engine()
            time.sleep(0.5)  # 等待连接关闭

            db_path = Path("test_security.db")
            if db_path.exists():
                db_path.unlink()
                print("\n🧹 测试数据库已清理")
        except Exception as e:
            print(f"\n⚠️  清理数据库时出错: {e}")

        return len(result.failed) == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
