"""
Data Sanitizer Module - 数据清洗模块
Provides protection against spreadsheet formula injection attacks.
"""

import re
from typing import Any, List, Union
import pandas as pd


# Characters that trigger formula execution in spreadsheets
FORMULA_TRIGGERS = ('=', '+', '-', '@', '\t', '\r', '\n')

# Pattern to detect potential formula injection
FORMULA_PATTERN = re.compile(r'^[\s]*[=+\-@]')


def sanitize_for_spreadsheet(value: Any) -> Any:
    """
    Sanitize a value to prevent spreadsheet formula injection.
    防止 Excel 公式注入攻击
    
    Dangerous characters (=, +, -, @) at the start of a cell
    can execute arbitrary commands when opened in Excel.
    
    Args:
        value: The value to sanitize
        
    Returns:
        Sanitized value with formula trigger prefixed by apostrophe
        
    Examples:
        >>> sanitize_for_spreadsheet("=SUM(A1:A10)")
        "'=SUM(A1:A10)"
        >>> sanitize_for_spreadsheet("+cmd|'/C calc")
        "'+cmd|'/C calc"
        >>> sanitize_for_spreadsheet("normal text")
        "normal text"
    """
    if value is None:
        return value
    
    # Only process strings
    if not isinstance(value, str):
        return value
    
    # Check if value starts with a formula trigger
    stripped = value.lstrip()
    if stripped and stripped[0] in FORMULA_TRIGGERS:
        # Prefix with apostrophe to prevent formula execution
        return "'" + value
    
    return value


def sanitize_dataframe_for_export(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitize all string columns in a DataFrame for safe spreadsheet export.
    批量清洗 DataFrame 中的所有字符串列
    
    Args:
        df: The DataFrame to sanitize
        
    Returns:
        New DataFrame with sanitized string values
    """
    result = df.copy()
    
    for column in result.columns:
        if result[column].dtype == 'object':
            result[column] = result[column].apply(sanitize_for_spreadsheet)
    
    return result


def sanitize_list(values: List[Any]) -> List[Any]:
    """
    Sanitize a list of values for spreadsheet export.
    
    Args:
        values: List of values to sanitize
        
    Returns:
        New list with sanitized values
    """
    return [sanitize_for_spreadsheet(v) for v in values]


def sanitize_dict(data: dict) -> dict:
    """
    Sanitize all string values in a dictionary.
    
    Args:
        data: Dictionary with potentially unsafe values
        
    Returns:
        New dictionary with sanitized string values
    """
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = sanitize_for_spreadsheet(value)
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[key] = sanitize_list(value)
        else:
            result[key] = value
    return result


def is_safe_for_spreadsheet(value: str) -> bool:
    """
    Check if a string value is safe for spreadsheet export.
    
    Args:
        value: The string to check
        
    Returns:
        True if safe, False if potentially dangerous
    """
    if not value or not isinstance(value, str):
        return True
    
    stripped = value.lstrip()
    return not (stripped and stripped[0] in FORMULA_TRIGGERS)


def remove_control_characters(value: str) -> str:
    """
    Remove control characters that might cause issues in spreadsheets.
    
    Args:
        value: The string to clean
        
    Returns:
        String with control characters removed
    """
    if not isinstance(value, str):
        return value
    
    # Remove most control characters except tab, newline, carriage return
    # which are handled by the sanitize function
    control_chars = ''.join(chr(i) for i in range(32) if i not in (9, 10, 13))
    return value.translate(str.maketrans('', '', control_chars))
