"""
Streamlit UI Pages - Streamlit 用户界面页面
Provides all UI components for the payroll management system.
"""

import os
import tempfile
from datetime import datetime, date
from typing import Optional, Dict, Any, List

import streamlit as st
import pandas as pd

from app.db import UserRole, EmployeeStatus
from app.services import (
    AuthService,
    EmployeeService,
    SalaryStructureService,
    PayrollService,
    ImportService,
    ExportService,
    SystemService,
)


# =============================================================================
# Session State Helpers
# =============================================================================

def get_current_user() -> Optional[Dict[str, Any]]:
    """Get the current logged-in user from session state."""
    return st.session_state.get("user")


def is_logged_in() -> bool:
    """Check if a user is logged in."""
    return get_current_user() is not None


def has_role(required_roles: List[UserRole]) -> bool:
    """Check if current user has one of the required roles."""
    user = get_current_user()
    if not user:
        return False
    return user.get("role") in [r.value for r in required_roles]


def logout():
    """Log out the current user."""
    if "user" in st.session_state:
        del st.session_state["user"]
    if "master_key" in st.session_state:
        del st.session_state["master_key"]


# =============================================================================
# Login Page
# =============================================================================

def render_login_page():
    """Render the login page."""
    st.title("🔐 薪酬管理系统")
    st.subheader("用户登录")
    
    # Check if system is initialized
    if not SystemService.is_initialized():
        render_setup_wizard()
        return
    
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录", use_container_width=True)
        
        if submitted:
            if not username or not password:
                st.error("请输入用户名和密码")
            else:
                success, user_data, message = AuthService.login(username, password)
                if success and user_data:
                    # user_data is already a dictionary
                    st.session_state["user"] = user_data
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def render_setup_wizard():
    """Render the initial setup wizard."""
    st.info("🎉 欢迎使用薪酬管理系统！请完成首次设置。")
    
    with st.form("setup_form"):
        st.subheader("步骤 1: 设置主密钥")
        st.warning("⚠️ 主密钥用于加密所有敏感数据，请务必安全保存！丢失主密钥将导致数据无法恢复。")
        master_key = st.text_input("主密钥（至少12个字符）", type="password")
        master_key_confirm = st.text_input("确认主密钥", type="password")
        
        st.subheader("步骤 2: 创建管理员账户")
        admin_username = st.text_input("管理员用户名（至少3个字符）")
        admin_password = st.text_input("管理员密码（至少8个字符）", type="password")
        admin_password_confirm = st.text_input("确认密码", type="password")
        
        submitted = st.form_submit_button("完成设置", use_container_width=True)
        
        if submitted:
            # Validation
            if len(master_key) < 12:
                st.error("主密钥至少需要12个字符")
            elif master_key != master_key_confirm:
                st.error("主密钥不匹配")
            elif len(admin_username) < 3:
                st.error("用户名至少需要3个字符")
            elif len(admin_password) < 8:
                st.error("密码至少需要8个字符")
            elif admin_password != admin_password_confirm:
                st.error("密码不匹配")
            else:
                # Initialize system
                success, message = SystemService.initialize_system(
                    master_key, admin_username, admin_password
                )
                if success:
                    st.session_state["master_key"] = master_key
                    st.success("系统初始化成功！请使用管理员账户登录。")
                    st.rerun()
                else:
                    st.error(message)


# =============================================================================
# Dashboard Page
# =============================================================================

def render_dashboard_page():
    """Render the main dashboard page."""
    st.title("📊 控制面板")
    
    user = get_current_user()
    st.write(f"欢迎，**{user['username']}** ({user['role']})")
    
    # Get statistics
    stats = SystemService.get_dashboard_stats()
    
    # Key metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("在职员工", stats.get("active_employees", 0))
    
    with col2:
        st.metric("系统用户", stats.get("total_users", 0))
    
    with col3:
        latest = stats.get("latest_payroll")
        if latest:
            st.metric(
                f"最近工资 ({latest['period']})",
                f"¥{latest['total_net']:,.2f}"
            )
        else:
            st.metric("最近工资", "暂无数据")
    
    st.divider()
    
    # Quick actions
    st.subheader("快速操作")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📥 导入数据", use_container_width=True):
            st.session_state["page"] = "import"
            st.rerun()
    
    with col2:
        if st.button("💰 工资计算", use_container_width=True):
            st.session_state["page"] = "payroll"
            st.rerun()
    
    with col3:
        if st.button("📤 导出报表", use_container_width=True):
            st.session_state["page"] = "export"
            st.rerun()
    
    with col4:
        if st.button("📋 审计日志", use_container_width=True):
            st.session_state["page"] = "audit"
            st.rerun()
    
    # Recent audit logs
    st.subheader("最近操作记录")
    logs = SystemService.get_audit_logs(limit=10)
    if logs:
        df = pd.DataFrame(logs)
        df = df[["created_at", "actor", "action", "result"]]
        df.columns = ["时间", "操作者", "操作", "结果"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无操作记录")


# =============================================================================
# Import Page
# =============================================================================

def render_import_page():
    """Render the data import page."""
    st.title("📥 数据导入")
    
    user = get_current_user()
    
    tab1, tab2, tab3, tab4 = st.tabs(["员工信息", "薪资结构", "考勤数据", "调整项"])
    
    with tab1:
        render_import_employees(user)
    
    with tab2:
        render_import_salary_structures(user)
    
    with tab3:
        render_import_attendance(user)
    
    with tab4:
        render_import_adjustments(user)


def _get_template_data(template_name: str) -> bytes:
    """Read template file data."""
    import os
    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), template_name)
    if os.path.exists(template_path):
        with open(template_path, "rb") as f:
            return f.read()
    # Fallback to current directory
    if os.path.exists(template_name):
        with open(template_name, "rb") as f:
            return f.read()
    return b""


def _process_uploaded_files(uploaded_files, import_func, user: Dict[str, Any], data_type: str):
    """Process multiple uploaded files."""
    if not uploaded_files:
        return
    
    # Handle single file or list of files
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]
    
    total_success = 0
    total_errors = []
    
    for uploaded_file in uploaded_files:
        try:
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.write(f"**{uploaded_file.name}** 预览数据：")
            st.dataframe(df.head(5), use_container_width=True)
            
        except Exception as e:
            st.error(f"文件 {uploaded_file.name} 读取失败: {str(e)}")
    
    if st.button(f"确认导入所有{data_type}", key=f"import_{data_type}_btn"):
        with st.spinner("正在导入..."):
            for uploaded_file in uploaded_files:
                try:
                    uploaded_file.seek(0)  # Reset file pointer
                    if uploaded_file.name.endswith(".csv"):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)
                    
                    success, message, count = import_func(df, user["username"])
                    if success:
                        total_success += count
                        st.success(f"{uploaded_file.name}: {message}")
                    else:
                        total_errors.append(f"{uploaded_file.name}: {message}")
                except Exception as e:
                    total_errors.append(f"{uploaded_file.name}: {str(e)}")
            
            if total_success > 0:
                st.success(f"✅ 总共成功导入 {total_success} 条记录")
            if total_errors:
                for err in total_errors:
                    st.error(err)


def render_import_employees(user: Dict[str, Any]):
    """Render employee import section."""
    st.subheader("导入员工信息")
    
    # Download template - read data first
    template_data = _get_template_data("employees_template.xlsx")
    if template_data:
        st.download_button(
            label="📥 下载模板",
            data=template_data,
            file_name="员工信息模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="emp_template_download"
        )
    
    st.write("**支持的列名**: 工号/员工编号, 姓名, 部门, 岗位, 入职日期, 银行卡号, 身份证号")
    
    # Multi-file upload
    uploaded_files = st.file_uploader(
        "选择 Excel 文件（支持多选）", 
        type=["xlsx", "xls", "csv"], 
        key="emp_upload",
        accept_multiple_files=True
    )
    
    _process_uploaded_files(uploaded_files, ImportService.import_employees, user, "员工信息")


def render_import_salary_structures(user: Dict[str, Any]):
    """Render salary structure import section."""
    st.subheader("导入薪资结构")
    
    template_data = _get_template_data("salary_structures_template.xlsx")
    if template_data:
        st.download_button(
            label="📥 下载模板",
            data=template_data,
            file_name="薪资结构模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="sal_template_download"
        )
    
    st.write("**支持的列名**: 工号/员工编号, 基本工资, 时薪, 加班倍率, 日扣款标准")
    
    uploaded_files = st.file_uploader(
        "选择 Excel 文件（支持多选）", 
        type=["xlsx", "xls", "csv"], 
        key="sal_upload",
        accept_multiple_files=True
    )
    
    _process_uploaded_files(uploaded_files, ImportService.import_salary_structures, user, "薪资结构")


def render_import_attendance(user: Dict[str, Any]):
    """Render attendance import section."""
    st.subheader("导入考勤数据")
    
    template_data = _get_template_data("attendance_template.xlsx")
    if template_data:
        st.download_button(
            label="📥 下载模板",
            data=template_data,
            file_name="考勤数据模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="att_template_download"
        )
    
    st.write("**支持的列名**: 工号/员工编号, 期间/月份, 工作天数/出勤天数, 加班小时, 缺勤天数")
    
    uploaded_files = st.file_uploader(
        "选择 Excel 文件（支持多选）", 
        type=["xlsx", "xls", "csv"], 
        key="att_upload",
        accept_multiple_files=True
    )
    
    _process_uploaded_files(uploaded_files, ImportService.import_attendance, user, "考勤数据")


def render_import_adjustments(user: Dict[str, Any]):
    """Render adjustments import section."""
    st.subheader("导入调整项")
    
    template_data = _get_template_data("adjustments_template.xlsx")
    if template_data:
        st.download_button(
            label="📥 下载模板",
            data=template_data,
            file_name="调整项模板.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="adj_template_download"
        )
    
    st.write("**支持的列名**: 工号/员工编号, 期间/月份, 类型(add/deduct), 金额, 原因/备注")
    
    uploaded_files = st.file_uploader(
        "选择 Excel 文件（支持多选）", 
        type=["xlsx", "xls", "csv"], 
        key="adj_upload",
        accept_multiple_files=True
    )
    
    _process_uploaded_files(uploaded_files, ImportService.import_adjustments, user, "调整项")




# =============================================================================
# Payroll Page
# =============================================================================

def render_payroll_page():
    """Render the payroll calculation page."""
    st.title("💰 工资计算")
    
    user = get_current_user()
    
    tab1, tab2 = st.tabs(["生成工资", "工资批次"])
    
    with tab1:
        render_generate_payroll(user)
    
    with tab2:
        render_payroll_runs(user)


def render_generate_payroll(user: Dict[str, Any]):
    """Render payroll generation section."""
    st.subheader("生成工资")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Period selection
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        year = st.selectbox("年份", range(current_year - 1, current_year + 2), index=1)
        month = st.selectbox("月份", range(1, 13), index=current_month - 1)
        
        period = f"{year}-{month:02d}"
    
    with col2:
        st.write("")
        st.write("")
        if st.button("🚀 生成工资", use_container_width=True, type="primary"):
            with st.spinner("正在计算工资..."):
                success, message, summary = PayrollService.generate_payroll(period, user["username"])
                if success and summary:
                    st.success(message)
                    st.metric("处理员工数", summary.total_employees)
                    st.metric("应发总额", f"¥{float(summary.total_gross):,.2f}")
                    st.metric("实发总额", f"¥{float(summary.total_net):,.2f}")
                else:
                    st.error(message)


def render_payroll_runs(user: Dict[str, Any]):
    """Render payroll runs list."""
    st.subheader("工资批次列表")
    
    runs = PayrollService.list_payroll_runs()
    
    if not runs:
        st.info("暂无工资批次")
        return
    
    for run in runs:
        with st.expander(f"📋 {run['period']} - {run['status']} ({run['total_employees']}人)"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**应发总额**: ¥{run['total_gross']:,.2f}")
                st.write(f"**实发总额**: ¥{run['total_net']:,.2f}")
            
            with col2:
                st.write(f"**生成者**: {run['generated_by']}")
                st.write(f"**生成时间**: {run['created_at'][:19]}")
            
            with col3:
                if run['status'] == 'draft':
                    if st.button("🔒 锁定", key=f"lock_{run['id']}"):
                        success, message = PayrollService.lock_payroll(run['id'], user['username'])
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                elif run['status'] == 'locked':
                    st.write(f"🔒 **已锁定** ({run['locked_at'][:10] if run['locked_at'] else ''})")
                    
                    if has_role([UserRole.ADMIN]):
                        if st.button("🔓 解锁", key=f"unlock_{run['id']}"):
                            if st.session_state.get(f"confirm_unlock_{run['id']}"):
                                success, message = PayrollService.unlock_payroll(
                                    run['id'], user['username'], confirmed=True
                                )
                                if success:
                                    st.success(message)
                                    del st.session_state[f"confirm_unlock_{run['id']}"]
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.session_state[f"confirm_unlock_{run['id']}"] = True
                                st.warning("再次点击确认解锁")
            
            # Show slips
            slips = PayrollService.get_payroll_slips(run['id'])
            if slips:
                df = pd.DataFrame(slips)
                display_cols = ['employee_no', 'employee_name', 'department', 
                               'gross_salary', 'total_deductions', 'net_salary']
                df_display = df[display_cols]
                df_display.columns = ['员工编号', '姓名', '部门', '应发工资', '扣款合计', '实发工资']
                st.dataframe(df_display, use_container_width=True, hide_index=True)


# =============================================================================
# Export Page
# =============================================================================

def render_export_page():
    """Render the export page."""
    st.title("📤 报表导出")
    
    user = get_current_user()
    
    runs = PayrollService.list_payroll_runs()
    
    if not runs:
        st.info("暂无可导出的工资批次")
        return
    
    # Select payroll run
    run_options = {f"{r['period']} ({r['status']})": r['id'] for r in runs}
    selected_run = st.selectbox("选择工资批次", list(run_options.keys()))
    run_id = run_options[selected_run]
    
    st.divider()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("📊 工资汇总表")
        if st.button("导出工资汇总", use_container_width=True):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                success, message, file_path, file_hash = ExportService.export_payroll_summary(
                    run_id, tmp.name, user["username"]
                )
                if success:
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "📥 下载文件",
                            f,
                            file_name=f"工资汇总_{selected_run.split()[0]}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    st.success(f"文件哈希: {file_hash[:16]}...")
                else:
                    st.error(message)
    
    with col2:
        st.subheader("🏦 银行转账清单")
        if st.button("导出银行清单", use_container_width=True):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                success, message, file_path, file_hash = ExportService.export_bank_transfer(
                    run_id, tmp.name, user["username"]
                )
                if success:
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "📥 下载文件",
                            f,
                            file_name=f"银行转账_{selected_run.split()[0]}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    st.success(f"文件哈希: {file_hash[:16]}...")
                else:
                    st.error(message)
    
    with col3:
        st.subheader("📝 会计凭证")
        if st.button("导出会计凭证", use_container_width=True):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                success, message, file_path, file_hash = ExportService.export_accounting_voucher(
                    run_id, tmp.name, user["username"]
                )
                if success:
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "📥 下载文件",
                            f,
                            file_name=f"会计凭证_{selected_run.split()[0]}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    st.success(f"文件哈希: {file_hash[:16]}...")
                else:
                    st.error(message)


# =============================================================================
# Reports Page
# =============================================================================

def render_reports_page():
    """Render the reports/analytics page."""
    st.title("📊 报表中心")
    
    # Get payroll runs for analysis
    runs = PayrollService.list_payroll_runs(limit=12)
    
    if not runs:
        st.info("暂无数据")
        return
    
    # Monthly cost trend
    st.subheader("月度人工成本趋势")
    
    df = pd.DataFrame(runs)
    df = df.sort_values("period")
    
    st.line_chart(df.set_index("period")["total_net"])
    
    # Summary statistics
    st.subheader("统计摘要")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("平均月度成本", f"¥{df['total_net'].mean():,.2f}")
    
    with col2:
        st.metric("最高月度成本", f"¥{df['total_net'].max():,.2f}")
    
    with col3:
        st.metric("总成本", f"¥{df['total_net'].sum():,.2f}")


# =============================================================================
# User Management Page
# =============================================================================

def render_user_management_page():
    """Render the user management page."""
    st.title("👥 用户管理")
    
    user = get_current_user()
    
    if not has_role([UserRole.ADMIN]):
        st.error("权限不足")
        return
    
    tab1, tab2 = st.tabs(["用户列表", "创建用户"])
    
    with tab1:
        render_user_list()
    
    with tab2:
        render_create_user(user)


def render_user_list():
    """Render user list."""
    from app.db import session_scope, UserRepository
    
    with session_scope() as session:
        users = UserRepository.list_all(session, active_only=False)
        
        data = []
        for u in users:
            data.append({
                "ID": u.id,
                "用户名": u.username,
                "角色": u.role.value,
                "状态": "启用" if u.is_active else "禁用",
                "最后登录": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "从未",
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_create_user(current_user: Dict[str, Any]):
    """Render create user form."""
    st.subheader("创建新用户")
    
    with st.form("create_user_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        role = st.selectbox("角色", [r.value for r in UserRole])
        
        submitted = st.form_submit_button("创建用户", use_container_width=True)
        
        if submitted:
            if not username or not password:
                st.error("请填写所有字段")
            else:
                role_enum = UserRole(role)
                success, message = AuthService.create_user(
                    username, password, role_enum, current_user["username"]
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)


# =============================================================================
# Audit Log Page
# =============================================================================

def render_audit_log_page():
    """Render the audit log page."""
    st.title("📋 审计日志")
    
    if not has_role([UserRole.ADMIN]):
        st.error("权限不足")
        return
    
    # Filters
    col1, col2 = st.columns(2)
    
    with col1:
        actor_filter = st.text_input("操作者筛选")
    
    with col2:
        action_filter = st.text_input("操作类型筛选")
    
    # Get logs
    logs = SystemService.get_audit_logs(
        limit=100,
        actor=actor_filter if actor_filter else None,
        action=action_filter if action_filter else None
    )
    
    if logs:
        df = pd.DataFrame(logs)
        df = df[["created_at", "actor", "action", "result", "resource_type", "resource_id"]]
        df.columns = ["时间", "操作者", "操作", "结果", "资源类型", "资源ID"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无日志记录")


# =============================================================================
# Settings Page
# =============================================================================

def render_settings_page():
    """Render the settings page."""
    st.title("⚙️ 系统设置")
    
    user = get_current_user()
    
    st.subheader("修改密码")
    
    with st.form("change_password_form"):
        new_password = st.text_input("新密码", type="password")
        confirm_password = st.text_input("确认新密码", type="password")
        
        submitted = st.form_submit_button("修改密码", use_container_width=True)
        
        if submitted:
            if not new_password:
                st.error("请输入新密码")
            elif new_password != confirm_password:
                st.error("密码不匹配")
            elif len(new_password) < 8:
                st.error("密码至少需要8个字符")
            else:
                success, message = AuthService.change_password(
                    user["id"], new_password, user["username"]
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    st.divider()
    
    # System info
    st.subheader("系统信息")
    st.write("- **版本**: 1.0.0")
    st.write("- **Python**: 3.11+")
    st.write("- **数据库**: SQLite")
