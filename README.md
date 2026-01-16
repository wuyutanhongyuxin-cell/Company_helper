# 薪酬管理系统 (Payroll Management System)

[![CI](https://github.com/wuyutanhongyuxin-cell/Company_helper/actions/workflows/ci.yml/badge.svg)](https://github.com/wuyutanhongyuxin-cell/Company_helper/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

一款专为中小企业设计的**离线安全薪酬管理工具**，基于 Windows 平台运行，具备企业级数据加密和完整的审计追踪功能。

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/wuyutanhongyuxin-cell/Company_helper.git
cd Company_helper

# 安装依赖
setup.bat

# 启动系统
run.bat
```

浏览器访问 http://localhost:8501 即可使用。

---


## 目录

1. [系统概述](#系统概述)
2. [系统要求](#系统要求)
3. [安装指南](#安装指南)
4. [首次使用](#首次使用)
5. [功能说明](#功能说明)
6. [安全特性](#安全特性)
7. [数据备份与恢复](#数据备份与恢复)
8. [故障排除](#故障排除)
9. [常见问题](#常见问题)

---

## 系统概述

本系统是一款**完全离线运行**的薪酬管理工具，专为财务人员和HR设计，无需联网即可完成以下工作：

- 员工信息管理（含银行卡号、身份证号加密存储）
- 薪资结构配置（基本工资、时薪、加班倍率、扣款标准等）
- 考勤数据导入（工作天数、加班小时、缺勤天数）
- 工资计算与批次管理（自动计算、锁定防篡改）
- 多种报表导出（工资汇总、银行转账清单、会计凭证）
- 完整的操作审计日志

### 核心优势

| 特性 | 说明 |
|------|------|
| 🔒 数据安全 | 数据库加密 + 字段级加密 + 文件加密三重保护 |
| 🖥️ 离线运行 | 无需网络连接，数据不外传 |
| 📊 简单易用 | 基于浏览器的图形界面，无需学习命令行 |
| 📁 导入导出 | 支持 Excel/CSV 格式，与现有流程无缝对接 |
| 📝 审计追踪 | 所有敏感操作均有记录，支持合规审查 |

---

## 系统要求

### 硬件要求

- **处理器**：Intel Core i3 或同等性能以上
- **内存**：4GB RAM（建议 8GB）
- **硬盘**：500MB 可用空间

### 软件要求

- **操作系统**：Windows 10 / Windows 11（64位）
- **Python**：3.11 或更高版本
- **浏览器**：Chrome / Edge / Firefox（最新版本）

### Python 安装

如果尚未安装 Python，请从官网下载：https://www.python.org/downloads/

> ⚠️ **重要**：安装时务必勾选 **"Add Python to PATH"** 选项！

验证安装：
```cmd
python --version
```
应显示 `Python 3.11.x` 或更高版本。

---

## 安装指南

### 方式一：使用安装脚本（推荐）

1. 将整个 `payroll_tool` 文件夹复制到目标位置（如 `D:\PayrollSystem\`）

2. 双击运行 `setup.bat`

3. 等待安装完成，看到以下提示表示成功：
   ```
   ============================================
   安装完成！
   运行 run.bat 启动系统
   ============================================
   ```

4. 如果安装过程中出现 SQLCipher 相关错误，请参考 [故障排除](#sqlcipher-安装失败) 章节

### 方式二：手动安装

```cmd
cd D:\PayrollSystem\payroll_tool

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

---

## 首次使用

### 第一步：启动系统

双击 `run.bat`，系统将自动：
1. 激活 Python 虚拟环境
2. 启动 Streamlit 服务
3. 在浏览器中打开系统界面

如果浏览器没有自动打开，请手动访问：http://localhost:8501

### 第二步：设置主密钥

首次启动时，系统会要求您设置**主密钥 (Master Key)**：

```
请输入主密钥（首次使用请设置一个强密码）
[________________]
```

> ⚠️ **极其重要**：主密钥是加密所有数据的根密钥，请务必：
> - 使用至少 12 位的强密码（包含大小写字母、数字、符号）
> - 将主密钥安全备份（如写在纸上锁入保险柜）
> - **丢失主密钥将导致所有数据永久无法恢复！**

### 第三步：创建管理员账户

输入主密钥后，系统会提示创建首个管理员账户：

- **用户名**：建议使用员工工号或姓名拼音
- **密码**：至少 8 位，建议包含大小写字母和数字

### 第四步：登录系统

使用刚创建的管理员账户登录，即可开始使用系统。

---

## 功能说明

### 📥 数据导入

系统支持从 Excel/CSV 文件批量导入以下数据：

| 数据类型 | 模板文件 | 说明 |
|----------|----------|------|
| 员工信息 | `employees_template.xlsx` | 员工编号、姓名、部门、入职日期、银行卡号、身份证号 |
| 薪资结构 | `salary_structures_template.xlsx` | 基本工资、时薪、加班倍率、日扣款标准、津贴、固定扣款 |
| 考勤数据 | `attendance_template.xlsx` | 期间(月份)、工作天数、加班小时、缺勤天数 |
| 调整项 | `adjustments_template.xlsx` | 奖金、补贴、罚款等临时调整 |

**导入步骤**：
1. 从系统下载对应模板
2. 按模板格式填写数据
3. 在"数据导入"页面上传文件
4. 预览并确认导入

> 💡 所有上传的源文件会被加密存储在 `vault/` 目录，便于日后审计追溯。

### 💰 工资计算

**计算公式**：
```
应发工资 = 基本工资 + 加班费 + 津贴 + 临时增项
加班费 = 加班小时 × 时薪 × 加班倍率
应扣金额 = 缺勤扣款 + 固定扣款 + 临时扣项 + 个税 + 社保
实发工资 = 应发工资 - 应扣金额
```

**操作步骤**：
1. 进入"工资计算"页面
2. 选择计算期间（如 2024-01）
3. 点击"生成工资"按钮
4. 查看计算结果和汇总统计

### 🔐 锁定与解锁

为防止工资数据被意外修改，系统提供**锁定机制**：

- **锁定**：确认无误后锁定当月工资批次，锁定后无法修改
- **解锁**：仅管理员可解锁，需二次确认，操作会被记录到审计日志

### 📤 报表导出

| 报表类型 | 用途 | 格式 |
|----------|------|------|
| 工资汇总表 | 内部存档、管理层审批 | Excel |
| 银行转账清单 | 提交银行批量发放工资 | Excel |
| 会计凭证 | 财务入账 | Excel |
| 工资条 | 发放给员工本人 | PDF（开发中） |

> 🔒 导出的文件默认启用加密，需要密码才能打开。您也可以在导出时选择不加密。

### 📊 报表中心

提供可视化的薪酬分析图表：

- 月度人工成本趋势图
- 部门成本占比饼图
- 关键指标卡片（员工数、总支出、平均工资等）

### 👥 用户管理

系统支持多用户和角色权限管理：

| 角色 | 权限 |
|------|------|
| 管理员 (ADMIN) | 全部功能，包括用户管理、解锁工资批次、查看审计日志 |
| 财务 (FINANCE) | 工资计算、锁定、导出、查看敏感数据 |
| 人事 (HR) | 员工信息管理、考勤导入、查看脱敏数据 |
| 员工 (EMPLOYEE) | 仅查看本人工资条（规划中） |

### 📋 审计日志

所有敏感操作都会被记录，包括：

- 用户登录/登出
- 数据导入
- 工资计算
- 锁定/解锁操作
- 文件导出（含文件哈希值）
- 敏感数据访问

审计日志不可删除或修改，支持合规审查。

---

## 安全特性

### 1. 数据库加密 (SQLCipher)

系统默认使用 SQLCipher 对整个数据库文件进行 AES-256 加密。即使数据库文件被复制，没有主密钥也无法读取任何内容。

> 如果 SQLCipher 安装失败，系统会退回到标准 SQLite，但仍通过字段级加密保护敏感数据。

### 2. 密码安全 (Argon2id)

用户密码使用 **Argon2id** 算法哈希存储，这是目前最安全的密码哈希算法：

- 抗 GPU 暴力破解
- 抗侧信道攻击
- 内存硬函数，增加攻击成本

### 3. 字段级加密 (Fernet)

敏感字段（银行卡号、身份证号、工资明细）使用 **Fernet** 对称加密单独加密：

- 基于 AES-128-CBC
- 包含消息认证码 (HMAC)
- 防止数据被篡改

### 4. 文件加密

- 上传的源文件加密存储在 `vault/` 目录
- 导出的报表可选加密
- 文件名使用随机字符串，防止信息泄露

### 5. 公式注入防护

导出 Excel/CSV 时，系统会自动处理可能触发公式执行的危险字符：

```
=SUM(A1:A10)  →  '=SUM(A1:A10)
+cmd|'/C calc  →  '+cmd|'/C calc
```

这可以防止恶意数据在 Excel 中执行命令。

### 6. 登录保护

- **速率限制**：连续 5 次登录失败后锁定 5 分钟
- **会话管理**：关闭浏览器后自动登出

### 7. 密钥轮换

系统支持加密密钥轮换，旧密钥仍可解密历史数据：

```python
# 在 Python 控制台执行
from app.security.core import EncryptionManager
em = EncryptionManager("您的主密钥")
em.rotate_key()  # 生成新密钥并保留旧密钥
```

---

## 数据备份与恢复

### 备份内容

定期备份以下文件/目录：

| 路径 | 内容 | 重要性 |
|------|------|--------|
| `payroll.db` | 数据库文件 | ⭐⭐⭐ 极重要 |
| `encryption_keys.dat` | 加密密钥 | ⭐⭐⭐ 极重要 |
| `vault/` | 源文件加密存储 | ⭐⭐ 重要 |
| `exports/` | 导出的报表 | ⭐ 可选 |

### 备份方法

**方法一：手动复制**

将上述文件复制到安全的存储位置（如加密U盘、保险柜）。

**方法二：使用备份脚本**

```cmd
@echo off
set BACKUP_DIR=D:\PayrollBackup\%date:~0,4%%date:~5,2%%date:~8,2%
mkdir "%BACKUP_DIR%"
copy payroll.db "%BACKUP_DIR%\"
copy encryption_keys.dat "%BACKUP_DIR%\"
xcopy vault "%BACKUP_DIR%\vault\" /E /I
echo 备份完成：%BACKUP_DIR%
```

### 恢复方法

1. 停止系统（关闭浏览器和命令行窗口）
2. 将备份文件复制回原位置
3. 重新启动系统
4. 使用原主密钥登录

> ⚠️ 恢复时必须同时恢复 `payroll.db` 和 `encryption_keys.dat`，两者缺一不可。

---

## 故障排除

### SQLCipher 安装失败

**现象**：运行 `setup.bat` 时出现类似以下错误：
```
ERROR: Could not build wheels for sqlcipher3-binary
```

**解决方案**：

**方案一：使用 Conda 环境**

1. 安装 Miniconda：https://docs.conda.io/en/latest/miniconda.html

2. 创建 Conda 环境并安装 SQLCipher：
   ```cmd
   conda create -n payroll python=3.11
   conda activate payroll
   conda install -c conda-forge sqlcipher
   pip install -r requirements.txt
   ```

3. 使用 `run_conda.bat` 启动系统（如果 setup.bat 检测到安装失败会自动生成）

**方案二：使用标准 SQLite（不推荐）**

如果无法安装 SQLCipher，系统会自动退回到标准 SQLite。此时：
- 数据库文件本身不加密
- 敏感字段仍然加密（银行卡号、身份证号等）
- 建议将整个 `payroll_tool` 目录放在加密磁盘（如 BitLocker）中

### 浏览器无法打开

**现象**：运行 `run.bat` 后浏览器没有自动打开。

**解决方案**：
1. 手动打开浏览器
2. 访问 http://localhost:8501
3. 如果显示"无法访问"，检查命令行窗口是否有错误信息

### 忘记主密钥

**现象**：忘记主密钥，无法进入系统。

**解决方案**：

> ⚠️ **非常抱歉，如果丢失主密钥，加密数据将永久无法恢复。**

唯一的选择是：
1. 删除 `payroll.db` 和 `encryption_keys.dat`
2. 重新初始化系统
3. 重新导入所有数据

这就是为什么我们强烈建议将主密钥安全备份。

### 忘记用户密码

**现象**：忘记登录密码，但记得主密钥。

**解决方案**：

请联系管理员重置密码。如果您就是唯一的管理员：

1. 使用 SQLite 工具（如 DB Browser for SQLite）打开 `payroll.db`
2. 在 `users` 表中找到您的账户
3. 使用以下 Python 代码生成新密码哈希：
   ```python
   from app.security.core import PasswordManager
   pm = PasswordManager()
   new_hash = pm.hash_password("新密码")
   print(new_hash)
   ```
4. 将生成的哈希值更新到 `password_hash` 字段

### 导出文件打不开

**现象**：导出的 Excel 文件提示需要密码。

**解决方案**：

如果导出时启用了加密，需要使用导出时系统显示的密码打开文件。

如果忘记密码，只能重新导出（不勾选加密选项）。

### 端口被占用

**现象**：启动时提示 `Port 8501 is already in use`。

**解决方案**：

1. 关闭其他正在使用 8501 端口的程序
2. 或修改 `run.bat` 中的端口号：
   ```cmd
   streamlit run app.py --server.port 8502
   ```

---

## 常见问题

### Q: 数据存储在哪里？

A: 所有数据存储在 `payroll_tool` 目录下：
- `payroll.db` - 主数据库
- `vault/` - 加密的源文件
- `exports/` - 导出的报表

### Q: 可以多人同时使用吗？

A: 本系统设计为**单机离线使用**。虽然多个用户可以通过同一台电脑的浏览器访问，但不支持多台电脑同时访问同一个数据库。

### Q: 如何升级系统？

A: 
1. 备份当前数据（参考"数据备份"章节）
2. 用新版本文件覆盖旧文件（保留数据库和密钥文件）
3. 重新运行 `setup.bat` 安装新依赖
4. 启动系统

### Q: 支持哪些 Excel 格式？

A: 支持以下格式：
- `.xlsx` - Excel 2007+ 格式（推荐）
- `.xls` - Excel 97-2003 格式
- `.csv` - 逗号分隔值

### Q: 工资计算精度如何？

A: 系统使用 Python `Decimal` 类型进行所有金额计算，精度为小数点后两位，不会出现浮点数精度问题。

### Q: 审计日志可以删除吗？

A: 不可以。审计日志设计为只增不删，确保操作可追溯。如果确实需要清理历史日志，需要直接操作数据库，但这不推荐。

---

## 技术支持

如遇到本文档未涵盖的问题，请：

1. 检查命令行窗口的错误信息
2. 查看 `logs/` 目录下的日志文件（如果有）
3. 记录操作步骤和错误截图

---

## 版本信息

- **版本**：1.0.0
- **发布日期**：2024年1月
- **Python 版本要求**：3.11+
- **许可证**：内部使用

---

*本系统由 Claude AI 协助开发，专为中小企业薪酬管理设计。*
