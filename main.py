#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import argparse
import json
import sys
from datetime import datetime

# 存储用户选择的检测特征
USER_SELECTED_PATTERNS = None

def get_context_lines(lines, line_number, context=2):
    """获取代码上下文"""
    start = max(0, line_number - context - 1)
    end = min(len(lines), line_number + context)
    
    result = []
    for i in range(start, end):
        line_num = i + 1  # 行号从1开始
        prefix = '>' if line_num == line_number else ' '
        result.append(f"{prefix} {line_num:4d}: {lines[i]}")
    
    return '\n'.join(result)

# Define suspicious patterns that might indicate PHP file tampering
SUSPICIOUS_PATTERNS = [
    # Base64 encoded payloads (common in web shells)
    {
        'id': 1,
        'pattern': r'(?:eval|assert|system)\s*\(\s*(?:base64_decode|str_rot13)\s*\(',
        'type': 'Encoded Command Execution',
        'description': 'Potential execution of encoded/obfuscated code',
        'default': True
    },
    # Common web shell patterns
    {
        'id': 2,
        'pattern': r'(?:exec|shell_exec|passthru|system)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)\s*\[',
        'type': 'Command Injection',
        'description': 'Direct execution of user-controlled input',
        'default': False
    },
    # File operations that might indicate backdoors
    {
        'id': 3,
        'pattern': r'(?:file_get_contents|file_put_contents|fopen|readfile)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Suspicious File Operation',
        'description': 'File operations with user input',
        'default': False
    },
    # Create function from string (used for dynamic code execution)
    {
        'id': 4,
        'pattern': r'(?:create_function|ReflectionFunction)\s*\(\s*(?:\$|[\'\"])',
        'type': 'Dynamic Function Creation',
        'description': 'Dynamic function creation (potential code injection)',
        'default': False
    },
    # SQL injection vulnerabilities
    {
        'id': 5,
        'pattern': r'(?:mysql_query|mysqli_query)\s*\(.*?\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'SQL Injection Vulnerability',
        'description': 'Unsafe SQL query with user input',
        'default': False
    },
    # Execution via backticks
    {
        'id': 6,
        'pattern': r'`\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Command Execution',
        'description': 'Execution of shell commands via backticks',
        'default': False
    },
    # PHP's preg_replace with /e modifier (remote code execution)
    {
        'id': 7,
        'pattern': r'preg_replace\s*\(\s*[\'\"]/.*/e[\'\"]',
        'type': 'Code Execution',
        'description': 'Vulnerable preg_replace with /e modifier',
        'default': False
    },
    # Obfuscated variable names (common in malicious code)
    {
        'id': 8,
        'pattern': r'\$[a-zA-Z0-9_]{1,2}\s*=\s*[\'\"][a-zA-Z0-9+/=]+[\'\"]',
        'type': 'Code Obfuscation',
        'description': 'Potentially obfuscated variable assignments',
        'default': False
    },
    # Potentially malicious iframe insertion
    {
        'id': 9,
        'pattern': r'<\?php.*?<iframe.*?src\s*=\s*[\'\"]http',
        'type': 'Malicious Content',
        'description': 'PHP code inserting iframe to external source',
        'default': False
    },
    # Inclusion of remote files
    {
        'id': 10,
        'pattern': r'(?:include|require|include_once|require_once)\s*\(\s*[\'\"](?:https?:|ftp:|php:|data:)',
        'type': 'Remote File Inclusion',
        'description': 'Including content from remote URLs',
        'default': False
    },
    # $_REQUEST/$_GET/$_POST directly in eval()
    {
        'id': 11,
        'pattern': r'(?:eval|assert)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Direct Code Injection',
        'description': 'Direct execution of user input',
        'default': False
    },
    # Use of extract() on user input (can overwrite variables)
    {
        'id': 12,
        'pattern': r'extract\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Variable Manipulation',
        'description': 'Unsafe use of extract() with user input',
        'default': False
    },
    # File upload handling vulnerabilities
    {
        'id': 13,
        'pattern': r'\$_FILES.*?[\'\"]tmp_name[\'\"].*?move_uploaded_file',
        'type': 'Unsafe File Upload',
        'description': 'Potential unsafe file upload handler',
        'default': False
    },
    # Potentially suspicious hidden input
    {
        'id': 14,
        'pattern': r'<input.+?type\s*=\s*[\'\"]hidden[\'\"].+?value\s*=\s*[\'\"](?:http|eval|base64|PHNjcmlwdD|PHN2Zz|PHhtbD)',
        'type': 'Suspicious Hidden Input',
        'description': 'Hidden input with suspicious value',
        'default': False
    },
    # Code added at the very beginning or end of file (common tampering pattern)
    {
        'id': 15,
        'pattern': r'^<\?php.{0,10}(?:eval|assert|base64_decode|str_rot13)\s*\(.{0,30}',
        'type': 'Header Injection',
        'description': 'Suspicious code at file beginning',
        'default': False
    },
    # Content irregularities (large blocks of obfuscated code)
    {
        'id': 16,
        'pattern': r'[a-zA-Z0-9+/=]{100,}',
        'type': 'Encoded Data',
        'description': 'Large block of encoded data',
        'default': False
    },
    # 输出编码内容 (可能是二阶注入或隐藏的JavaScript)
    {
        'id': 17,
        'pattern': r'(?:echo|print|<?=)\s*(?:base64_decode|str_rot13)\s*\(',
        'type': 'Encoded Content Output',
        'description': 'Suspicious output of encoded/obfuscated content',
        'default': True
    },
    # 复杂解码链 (多重解码)
    {
        'id': 18,
        'pattern': r'(?:base64_decode|str_rot13|gzinflate|gzuncompress|gzdecode)\s*\(\s*(?:base64_decode|str_rot13|gzinflate|gzuncompress|gzdecode)',
        'type': 'Multi-layer Encoding',
        'description': 'Multiple layers of encoding (common in obfuscated malware)',
        'default': True
    },
    # 包含加密函数的可疑函数
    {
        'id': 19,
        'pattern': r'function\s+[a-zA-Z0-9_]+\s*\([^)]*\)\s*{[^}]*(?:base64_decode|str_rot13|gzinflate)[^}]*}',
        'type': 'Suspicious Function',
        'description': 'Function containing encoding/encryption operations',
        'default': True
    },
    # 变量赋值后直接输出编码内容
    {
        'id': 20,
        'pattern': r'\$[a-zA-Z0-9_]+\s*=\s*base64_decode\([^)]+\);\s*(?:echo|print)\s*\$[a-zA-Z0-9_]+',
        'type': 'Indirect Encoded Output',
        'description': 'Decode to variable then output (obfuscation technique)',
        'default': True
    },
    # 远程文件执行组合（eval+file_get_contents+base64_decode）
    {
        'id': 21,
        'pattern': r'eval\s*\([^)]*file_get_contents\s*\([^)]*base64_decode\s*\(',
        'type': 'Remote Code Execution',
        'description': 'Loading and executing code from encoded remote URL',
        'default': True
    },
    # 禁用错误显示+恶意代码组合（常见隐藏手法）
    {
        'id': 22,
        'pattern': r'(?:ini_set|error_reporting)\s*\([^)]*display_errors[^)]*\)[^;]*;\s*(?:eval|assert|system)',
        'type': 'Error Hiding + Code Execution',
        'description': 'Disabling error display before executing suspicious code',
        'default': True
    }
]


def scan_php_file(file_path):
    """Scan a PHP file for suspicious patterns."""
    suspicious_lines = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            lines = content.split('\n')
            
            # Check each defined pattern that user selected
            for pattern_info in USER_SELECTED_PATTERNS:
                pattern = pattern_info['pattern']
                issue_type = pattern_info['type']
                pattern_id = pattern_info['id']
                
                # First check the whole content for patterns that might span multiple lines
                if re.search(pattern, content, re.IGNORECASE):
                    # If found, identify the specific lines
                    for i, line in enumerate(lines, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            # 获取代码上下文
                            code_context = get_context_lines(lines, i)
                            
                            suspicious_lines.append({
                                'file_path': file_path,
                                'line_number': i,
                                'issue_type': issue_type,
                                'line_content': line.strip(),
                                'code_context': code_context,
                                'pattern_id': pattern_id
                            })
    except Exception as e:
        print(f"Error scanning {file_path}: {str(e)}")
    
    return suspicious_lines


def scan_directory(directory_path):
    """Recursively scan a directory for PHP files."""
    all_suspicious_lines = []
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.php'):
                file_path = os.path.join(root, file)
                suspicious_lines = scan_php_file(file_path)
                all_suspicious_lines.extend(suspicious_lines)
    
    return all_suspicious_lines


def save_to_csv(suspicious_lines, output_file):
    """Save scan results to a CSV file."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['序号', '疑似文件路径', '行号', '问题类型', '问题代码内容', '代码片段'])
        
        for i, item in enumerate(suspicious_lines, 1):
            writer.writerow([
                i,
                item['file_path'],
                item['line_number'],
                item['issue_type'],
                item['line_content'],
                item['code_context']
            ])


def print_results(suspicious_lines):
    """Print scan results to console."""
    if not suspicious_lines:
        print("没有发现疑似被篡改的PHP文件。")
        return
    
    print(f"\n发现 {len(suspicious_lines)} 处疑似问题:\n")
    print("{:<5} {:<50} {:<8} {:<25}".format("序号", "文件路径", "行号", "类型"))
    print("-" * 90)
    
    for i, item in enumerate(suspicious_lines, 1):
        print("{:<5} {:<50} {:<8} {:<25}".format(
            i, 
            item['file_path'] if len(item['file_path']) <= 50 else f"...{item['file_path'][-47:]}", 
            item['line_number'], 
            item['issue_type']
        ))
        print("\n代码片段:")
        print(item['code_context'])
        print("\n" + "-" * 90)


def select_patterns_interactive():
    """交互式选择要检测的模式"""
    global USER_SELECTED_PATTERNS
    
    print("\n请选择要检测的PHP安全漏洞特征：")
    print("-" * 50)
    
    selected_indices = []
    # 默认选择第一个特征
    default_selected = [pattern['id'] for pattern in SUSPICIOUS_PATTERNS if pattern['default']]
    
    for pattern in SUSPICIOUS_PATTERNS:
        selected_mark = "[X]" if pattern['default'] else "[ ]"
        print(f"{selected_mark} {pattern['id']:2d}. {pattern['type']} - {pattern['description']}")
    
    print("-" * 50)
    print("请输入要选择的特征ID（用逗号分隔），直接回车使用默认选择，输入'all'选择全部：")
    user_input = input("> ").strip()
    
    if user_input.lower() == 'all':
        selected_indices = [pattern['id'] for pattern in SUSPICIOUS_PATTERNS]
    elif user_input == "":
        selected_indices = default_selected
    else:
        try:
            selected_indices = [int(idx.strip()) for idx in user_input.split(',')]
        except ValueError:
            print("输入格式不正确，将使用默认选择")
            selected_indices = default_selected
    
    # 根据选择筛选模式
    USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['id'] in selected_indices]
    
    print(f"\n已选择 {len(USER_SELECTED_PATTERNS)} 个特征进行检测")
    for pattern in USER_SELECTED_PATTERNS:
        print(f"  {pattern['id']:2d}. {pattern['type']}")
    
    # 防止用户没有选择任何特征
    if not USER_SELECTED_PATTERNS:
        print("\n警告：未选择任何特征，将使用默认特征继续")
        USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['default']]


def save_patterns_selection(selected_patterns, filename=".pattern_selection.json"):
    """保存用户选择的模式到文件"""
    selection = [pattern['id'] for pattern in selected_patterns]
    with open(filename, 'w') as f:
        json.dump(selection, f)
    print(f"已保存特征选择到 {filename}")


def load_patterns_selection(filename=".pattern_selection.json"):
    """从文件加载用户选择的模式"""
    global USER_SELECTED_PATTERNS
    try:
        with open(filename, 'r') as f:
            selected_ids = json.load(f)
        USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['id'] in selected_ids]
        print(f"已从 {filename} 加载特征选择（{len(USER_SELECTED_PATTERNS)} 个特征）")
        return True
    except (FileNotFoundError, json.JSONDecodeError):
        return False


def main():
    global USER_SELECTED_PATTERNS
    
    parser = argparse.ArgumentParser(description='扫描PHP文件是否存在安全威胁或被篡改的迹象')
    parser.add_argument('directory', help='要扫描的目录路径')
    parser.add_argument('-o', '--output', default=f'php_security_scan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', 
                        help='输出CSV文件名 (默认: php_security_scan_时间戳.csv)')
    parser.add_argument('-p', '--patterns', help='使用特定的特征ID（逗号分隔，例如 "1,3,5"）')
    parser.add_argument('--load', action='store_true', help='加载上次保存的特征选择')
    parser.add_argument('--non-interactive', action='store_true', help='非交互模式，使用默认特征')
    args = parser.parse_args()
    
    # 确定使用哪些检测特征
    if args.patterns:
        try:
            pattern_ids = [int(idx.strip()) for idx in args.patterns.split(',')]
            USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['id'] in pattern_ids]
            if not USER_SELECTED_PATTERNS:
                print("未找到指定的特征ID，将使用默认特征")
                USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['default']]
        except ValueError:
            print("特征ID格式不正确，将使用默认特征")
            USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['default']]
    elif args.load:
        # 尝试加载保存的选择
        if not load_patterns_selection():
            print("未找到保存的特征选择，将使用默认特征")
            USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['default']]
    elif not args.non_interactive and sys.stdin.isatty():  # 仅在交互式终端中启用交互
        select_patterns_interactive()
        # 保存选择以便将来使用
        save_patterns_selection(USER_SELECTED_PATTERNS)
    else:
        # 非交互模式，使用默认特征
        USER_SELECTED_PATTERNS = [pattern for pattern in SUSPICIOUS_PATTERNS if pattern['default']]
    
    print(f"开始扫描目录: {args.directory}")
    print(f"使用 {len(USER_SELECTED_PATTERNS)} 个特征进行检测")
    
    suspicious_lines = scan_directory(args.directory)
    print(f"扫描完成，共处理{sum(1 for _ in os.walk(args.directory) for f in _[2] if f.endswith('.php'))}个PHP文件")
    
    print_results(suspicious_lines)
    save_to_csv(suspicious_lines, args.output)
    
    print(f"\n详细结果已保存到: {args.output}")


if __name__ == '__main__':
    main()