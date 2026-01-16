"""
Payroll Management System - 薪酬管理系统
Main Streamlit Application Entry Point
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure Streamlit page
st.set_page_config(
    page_title="薪酬管理系统",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize database on first run
from app.db import init_database_simple, create_all_tables

@st.cache_resource
def initialize_database():
    """Initialize database (cached to run only once)."""
    engine = init_database_simple()
    create_all_tables(engine)
    return True

initialize_database()

# Import UI pages
from app.ui import (
    render_login_page,
    render_dashboard_page,
    render_import_page,
    render_payroll_page,
    render_export_page,
    render_reports_page,
    render_user_management_page,
    render_audit_log_page,
    render_settings_page,
)
from app.ui.pages import is_logged_in, logout, has_role, get_current_user
from app.db import UserRole


def main():
    """Main application entry point."""
    
    # Check if master key is set (required for encryption)
    if "master_key" not in st.session_state:
        # Try to get from environment for development
        env_key = os.environ.get("TEST_MASTER_KEY")
        if env_key:
            st.session_state["master_key"] = env_key
            # Initialize encryption manager
            from app.security.core import get_encryption_manager
            try:
                get_encryption_manager(env_key)
            except:
                pass
    
    # Check login status
    if not is_logged_in():
        render_login_page()
        return
    
    # Sidebar navigation
    with st.sidebar:
        st.title("💰 薪酬管理系统")
        st.divider()
        
        user = get_current_user()
        st.write(f"👤 {user['username']}")
        st.write(f"🔑 {user['role']}")
        
        st.divider()
        
        # Page mapping for quick action buttons
        page_mapping = {
            "import": "📥 数据导入",
            "payroll": "💰 工资计算",
            "export": "📤 报表导出",
            "audit": "📋 审计日志",
        }
        
        # Get current page from session state (set by quick action buttons)
        page_options = [
            "📊 控制面板",
            "📥 数据导入",
            "💰 工资计算",
            "📤 报表导出",
            "📈 报表中心",
            "👥 用户管理",
            "📋 审计日志",
            "⚙️ 系统设置",
        ]
        
        # Check if quick action button set a page
        quick_page = st.session_state.get("page")
        default_index = 0
        if quick_page and quick_page in page_mapping:
            target_page = page_mapping[quick_page]
            if target_page in page_options:
                default_index = page_options.index(target_page)
            # Clear the quick action page after using it
            del st.session_state["page"]
        
        # Navigation menu
        page = st.radio(
            "导航",
            options=page_options,
            index=default_index,
            label_visibility="collapsed",
        )
        
        st.divider()
        
        if st.button("🚪 退出登录", use_container_width=True):
            logout()
            st.rerun()
    
    # Render selected page
    if page == "📊 控制面板":
        render_dashboard_page()
    elif page == "📥 数据导入":
        render_import_page()
    elif page == "💰 工资计算":
        render_payroll_page()
    elif page == "📤 报表导出":
        render_export_page()
    elif page == "📈 报表中心":
        render_reports_page()
    elif page == "👥 用户管理":
        render_user_management_page()
    elif page == "📋 审计日志":
        render_audit_log_page()
    elif page == "⚙️ 系统设置":
        render_settings_page()


if __name__ == "__main__":
    main()
