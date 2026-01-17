# 安全修复报告 - Security Fixes Report

**日期**: 2026-01-17
**版本**: v1.1.0-security-fixes

## 修复的关键安全问题

### 🔴 严重问题（Critical）

#### 1. 时序攻击漏洞修复 (Timing Attack Protection)
**文件**: `app/services/business.py` - `AuthService.login()`

**问题描述**:
- 原实现中，用户不存在时立即返回，用户存在时需验证密码
- 攻击者可通过响应时间差异枚举有效用户名

**修复方案**:
- ✅ 无论用户是否存在都执行密码哈希验证（使用假哈希）
- ✅ 统一错误消息，不泄露账户状态信息
- ✅ 防止通过错误消息和时序推断用户名有效性

**代码变更**:
```python
# 修复前：用户不存在时立即返回
if user is None:
    return False, None, "用户名或密码错误"

# 修复后：始终执行密码验证
if user is None:
    dummy_hash = "$argon2id$..."
    pm.verify_password(password, dummy_hash)
    return False, None, "用户名或密码错误"
```

---

#### 2. 财务计算精度丢失修复 (Decimal Precision Fix)
**文件**: `app/services/business.py` - `PayrollService._calculate_slip()`

**问题描述**:
- 津贴、扣款、调整项未量化到2位小数
- 多个高精度数值相加可能产生累积误差（如 0.0000001 元）
- 年度汇总时可能被审计发现

**修复方案**:
- ✅ 定义统一的 `quantize_money()` 函数
- ✅ 所有金额计算后立即量化到 `0.01` 元
- ✅ 确保应发工资、应扣总额、实发工资精度一致

**代码变更**:
```python
def quantize_money(value: Decimal) -> Decimal:
    """量化金额到2位小数"""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# 所有计算都量化
allowances_total = quantize_money(sum(...))
gross_salary = quantize_money(base_salary + overtime_pay + allowances_total + adj_add)
net_salary = quantize_money(gross_salary - total_deductions)
```

---

#### 3. 考勤逻辑矛盾修复 (Attendance Logic Fix)
**文件**: `app/services/business.py` - `PayrollService.generate_payroll()`

**问题描述**:
- 员工没有考勤记录时，被当作"0缺勤、0加班"处理
- 导致没打卡的员工仍拿全额工资

**修复方案**:
- ✅ 强制要求员工必须有考勤记录才能生成工资
- ✅ 无考勤记录的员工会被跳过，并记录到审计日志
- ✅ 返回消息中明确显示跳过的员工列表

**代码变更**:
```python
# 新增：检查考勤记录
attendance = AttendanceRepository.get_by_employee_period(session, employee.id, period)
if not attendance:
    employees_without_attendance.append(f"{employee.name}({employee.employee_no})")
    continue  # 跳过

# 审计日志记录
if employees_without_attendance:
    AuditLogRepository.create(..., metadata={"warning": ..., "skipped_employees": ...})
```

---

### 🟡 高优先级问题（High Priority）

#### 4. 加密管理器线程安全修复 (Thread-Safe Encryption Manager)
**文件**: `app/security/core.py` - `get_encryption_manager()`

**问题描述**:
- 全局单例模式在多线程环境下存在竞态条件
- 可能导致多个线程同时创建加密实例
- 密钥来源混乱（环境变量、session_state、参数）

**修复方案**:
- ✅ 使用双重检查锁定模式（Double-Checked Locking）
- ✅ 添加 `threading.Lock` 保护单例初始化
- ✅ 明确密钥来源优先级：session_state > 测试环境变量
- ✅ 移除生产环境自动读取 `TEST_MASTER_KEY`

**代码变更**:
```python
_encryption_lock = Lock()

def get_encryption_manager(master_key: Optional[str] = None) -> EncryptionManager:
    global _encryption_manager

    if _encryption_manager is None:
        with _encryption_lock:
            if _encryption_manager is None:  # 双重检查
                # 初始化逻辑
                ...
```

---

#### 5. 工资解锁机制改进 (Payroll Unlock Enhancement)
**文件**: `app/services/business.py` - `PayrollService.unlock_payroll()`

**问题描述**:
- 任何有权限的人都可以解锁工资批次
- 缺少解锁理由，无法追溯原因
- 审计日志不够详细

**修复方案**:
- ✅ 强制要求提供解锁理由（最少10个字符）
- ✅ 记录解锁前的完整数据状态（金额、锁定人、锁定时间）
- ✅ 使用高优先级审计动作 `unlock_payroll_critical`
- ✅ 审计日志包含原始数据快照，便于事后审查

**API 变更**:
```python
# 修复前
unlock_payroll(run_id: int, actor: str, confirmed: bool = False)

# 修复后（增加 reason 参数）
unlock_payroll(run_id: int, actor: str, reason: str, confirmed: bool = False)
```

---

#### 6. 导入错误处理优化 (Import Error Handling)
**文件**: `app/services/business.py` - `ImportService.import_employees()`

**问题描述**:
- 部分行失败时仍返回 `True`，用户误以为全部成功
- 错误信息只显示前5个，大量失败时信息不足
- 没有区分"全部成功"、"部分成功"、"全部失败"

**修复方案**:
- ✅ 返回详细的导入统计（成功数/总数）
- ✅ 区分三种结果状态，返回不同消息
- ✅ 失败时显示前10个错误（原为5个）
- ✅ 明确提示失败行数和总行数

**返回消息改进**:
```python
# 全部成功
"全部成功：导入 50 名员工"

# 部分成功
"部分成功：导入 45/50 名员工，5 行失败。错误: ..."

# 全部失败
"导入失败，所有 50 行都失败: ..."
```

---

## 其他改进

### 代码质量提升
- ✅ 添加更详细的注释和文档
- ✅ 统一错误消息格式
- ✅ 改进审计日志元数据结构

### 合规性增强
- ✅ 审计日志包含更多上下文信息
- ✅ 关键操作（解锁工资）强制要求说明理由
- ✅ 财务数据精度符合会计准则

---

## 未修复的低优先级问题

以下问题建议在后续版本中修复：

1. **密码强度验证不足** - 应要求包含大小写、数字、特殊字符
2. **UTC 时间戳已弃用** - Python 3.12+ 应使用 `datetime.now(timezone.utc)`
3. **外键约束未配置级联** - 删除员工前需手动删除关联用户
4. **审计日志缺少完整性保护** - 建议使用哈希链或数字签名防篡改
5. **密钥轮换功能未完善** - 旧数据不会自动重新加密

---

## 测试建议

修复后应进行以下测试：

### 安全测试
- [ ] 时序攻击测试：验证不同场景下响应时间一致性
- [ ] 并发测试：多线程同时调用加密服务
- [ ] 精度测试：工资计算的累积误差检查

### 功能测试
- [ ] 无考勤记录的员工不应生成工资
- [ ] 工资解锁必须提供理由
- [ ] 导入部分失败时返回正确状态

### 回归测试
- [ ] 现有员工导入流程
- [ ] 工资计算准确性
- [ ] 审计日志完整性

---

## 版本兼容性

- ✅ 向后兼容：已有数据库无需迁移
- ⚠️ API 变更：`unlock_payroll()` 新增必填参数 `reason`
- ✅ Python 版本：3.9+ （建议升级到 3.11+）

---

## 贡献者

- Claude Sonnet 4.5 (安全审计与修复)
- 修复日期: 2026-01-17

---

## 参考资料

- OWASP Top 10 (2021)
- CWE-208: Observable Timing Discrepancy
- IEEE 754-2019: Floating Point Arithmetic
- ISO/IEC 27001: Information Security Management
