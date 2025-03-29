#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import csv
import argparse
from datetime import datetime

# Define suspicious patterns that might indicate PHP file tampering
SUSPICIOUS_PATTERNS = [
    # Base64 encoded payloads (common in web shells)
    {
        'pattern': r'(?:eval|assert|system)\s*\(\s*(?:base64_decode|str_rot13)\s*\(',
        'type': 'Encoded Command Execution',
        'description': 'Potential execution of encoded/obfuscated code'
    },
    # Common web shell patterns
    {
        'pattern': r'(?:exec|shell_exec|passthru|system)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)\s*\[',
        'type': 'Command Injection',
        'description': 'Direct execution of user-controlled input'
    },
    # File operations that might indicate backdoors
    {
        'pattern': r'(?:file_get_contents|file_put_contents|fopen|readfile)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Suspicious File Operation',
        'description': 'File operations with user input'
    },
    # Create function from string (used for dynamic code execution)
    {
        'pattern': r'(?:create_function|ReflectionFunction)\s*\(\s*(?:\$|[\'\"]).*?\)',
        'type': 'Dynamic Function Creation',
        'description': 'Dynamic function creation (potential code injection)'
    },
    # SQL injection vulnerabilities
    {
        'pattern': r'(?:mysql_query|mysqli_query)\s*\(.*?\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'SQL Injection Vulnerability',
        'description': 'Unsafe SQL query with user input'
    },
    # Execution via backticks
    {
        'pattern': r'`\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Command Execution',
        'description': 'Execution of shell commands via backticks'
    },
    # PHP's preg_replace with /e modifier (remote code execution)
    {
        'pattern': r'preg_replace\s*\(\s*[\'\"]/.*/e[\'\"]',
        'type': 'Code Execution',
        'description': 'Vulnerable preg_replace with /e modifier'
    },
    # Obfuscated variable names (common in malicious code)
    {
        'pattern': r'\$[a-zA-Z0-9_]{1,2}\s*=\s*[\'\"][a-zA-Z0-9+/=]+[\'\"]',
        'type': 'Code Obfuscation',
        'description': 'Potentially obfuscated variable assignments'
    },
    # Potentially malicious iframe insertion
    {
        'pattern': r'<\?php.*?<iframe.*?src\s*=\s*[\'\"]http',
        'type': 'Malicious Content',
        'description': 'PHP code inserting iframe to external source'
    },
    # Inclusion of remote files
    {
        'pattern': r'(?:include|require|include_once|require_once)\s*\(\s*[\'\"](?:https?:|ftp:|php:|data:)',
        'type': 'Remote File Inclusion',
        'description': 'Including content from remote URLs'
    },
    # $_REQUEST/$_GET/$_POST directly in eval()
    {
        'pattern': r'(?:eval|assert)\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Direct Code Injection',
        'description': 'Direct execution of user input'
    },
    # Use of extract() on user input (can overwrite variables)
    {
        'pattern': r'extract\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)',
        'type': 'Variable Manipulation',
        'description': 'Unsafe use of extract() with user input'
    },
    # File upload handling vulnerabilities
    {
        'pattern': r'\$_FILES.*?[\'\"]tmp_name[\'\"].*?move_uploaded_file',
        'type': 'Unsafe File Upload',
        'description': 'Potential unsafe file upload handler'
    },
    # Potentially suspicious hidden input
    {
        'pattern': r'<input.+?type\s*=\s*[\'\"]hidden[\'\"].+?value\s*=\s*[\'\"](?:http|eval|base64|PHNjcmlwdD|PHN2Zz|PHhtbD)',
        'type': 'Suspicious Hidden Input',
        'description': 'Hidden input with suspicious value'
    },
    # Code added at the very beginning or end of file (common tampering pattern)
    {
        'pattern': r'^<\?php.{0,10}(?:eval|assert|base64_decode|str_rot13)\s*\(.{0,30}',
        'type': 'Header Injection',
        'description': 'Suspicious code at file beginning'
    },
    # Content irregularities (large blocks of obfuscated code)
    {
        'pattern': r'[a-zA-Z0-9+/=]{100,}',
        'type': 'Encoded Data',
        'description': 'Large block of encoded data'
    }
]


def scan_php_file(file_path):
    """Scan a PHP file for suspicious patterns."""
    suspicious_lines = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
            lines = content.split('\n')
            
            # Check each defined pattern
            for pattern_info in SUSPICIOUS_PATTERNS:
                pattern = pattern_info['pattern']
                issue_type = pattern_info['type']
                
                # First check the whole content for patterns that might span multiple lines
                if re.search(pattern, content, re.IGNORECASE):
                    # If found, identify the specific lines
                    for i, line in enumerate(lines, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            suspicious_lines.append({
                                'file_path': file_path,
                                'line_number': i,
                                'issue_type': issue_type,
                                'line_content': line.strip()
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
        writer.writerow(['序号', '疑似文件路径', '行号', '类型', '内容'])
        
        for i, item in enumerate(suspicious_lines, 1):
            writer.writerow([
                i,
                item['file_path'],
                item['line_number'],
                item['issue_type'],
                item['line_content']
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


def main():
    parser = argparse.ArgumentParser(description='扫描PHP文件是否存在安全威胁或被篡改的迹象')
    parser.add_argument('directory', help='要扫描的目录路径')
    parser.add_argument('-o', '--output', default=f'php_security_scan_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv', 
                        help='输出CSV文件名 (默认: php_security_scan_时间戳.csv)')
    args = parser.parse_args()
    
    print(f"开始扫描目录: {args.directory}")
    suspicious_lines = scan_directory(args.directory)
    print(f"扫描完成，共处理{sum(1 for _ in os.walk(args.directory) for f in _[2] if f.endswith('.php'))}个PHP文件")
    
    print_results(suspicious_lines)
    save_to_csv(suspicious_lines, args.output)
    
    print(f"\n详细结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
