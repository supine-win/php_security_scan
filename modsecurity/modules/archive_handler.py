#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归档文件处理模块
负责解压tar.gz, zip等归档文件
"""

import os
import subprocess
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger('modsecurity_installer')

def extract_archive(archive_file, extract_dir):
    """解压归档文件
    
    Args:
        archive_file (str): 归档文件路径
        extract_dir (str): 解压目录
        
    Returns:
        bool: 是否成功解压
    """
    try:
        # 检查归档文件是否存在
        if not os.path.exists(archive_file):
            logger.error(f"归档文件不存在: {archive_file}")
            return False
        
        # 确保解压目录存在
        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir)
        
        logger.info(f"解压 {archive_file} 到 {extract_dir}")
        
        # 获取归档文件类型
        file_ext = os.path.splitext(archive_file)[1].lower()
        
        # 根据文件类型选择解压命令
        if archive_file.endswith('.tar.gz') or archive_file.endswith('.tgz'):
            cmd = f"tar -xzf {archive_file} -C {extract_dir}"
        elif archive_file.endswith('.tar.bz2') or archive_file.endswith('.tbz2'):
            cmd = f"tar -xjf {archive_file} -C {extract_dir}"
        elif archive_file.endswith('.tar'):
            cmd = f"tar -xf {archive_file} -C {extract_dir}"
        elif archive_file.endswith('.zip'):
            cmd = f"unzip -q {archive_file} -d {extract_dir}"
        else:
            logger.error(f"不支持的归档格式: {archive_file}")
            return False
        
        # 执行解压命令
        process = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 检查解压结果
        if process.returncode == 0:
            logger.info(f"成功解压 {archive_file}")
            return True
        else:
            logger.error(f"解压失败: {process.stderr.decode() if process.stderr else 'Unknown error'}")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"解压文件时发生错误: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"解压文件时发生未知错误: {e}")
        return False


def create_archive(source_dir, archive_file, archive_type='tar.gz'):
    """创建归档文件
    
    Args:
        source_dir (str): 源目录路径
        archive_file (str): 归档文件路径
        archive_type (str): 归档类型 (tar.gz, zip)
        
    Returns:
        bool: 是否成功创建归档
    """
    try:
        # 检查源目录是否存在
        if not os.path.exists(source_dir):
            logger.error(f"源目录不存在: {source_dir}")
            return False
        
        # 确保归档文件的目录存在
        archive_dir = os.path.dirname(archive_file)
        if archive_dir and not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        
        logger.info(f"创建归档: {source_dir} -> {archive_file}")
        
        # 根据归档类型选择命令
        if archive_type == 'tar.gz' or archive_type == 'tgz':
            cmd = f"tar -czf {archive_file} -C {os.path.dirname(source_dir)} {os.path.basename(source_dir)}"
        elif archive_type == 'tar.bz2' or archive_type == 'tbz2':
            cmd = f"tar -cjf {archive_file} -C {os.path.dirname(source_dir)} {os.path.basename(source_dir)}"
        elif archive_type == 'tar':
            cmd = f"tar -cf {archive_file} -C {os.path.dirname(source_dir)} {os.path.basename(source_dir)}"
        elif archive_type == 'zip':
            # 切换到父目录以便zip只包含目标目录
            parent_dir = os.path.dirname(source_dir)
            dir_name = os.path.basename(source_dir)
            cmd = f"cd {parent_dir} && zip -r {archive_file} {dir_name}"
        else:
            logger.error(f"不支持的归档类型: {archive_type}")
            return False
        
        # 执行归档命令
        process = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 检查结果
        if process.returncode == 0:
            logger.info(f"成功创建归档 {archive_file}")
            return True
        else:
            logger.error(f"创建归档失败: {process.stderr.decode() if process.stderr else 'Unknown error'}")
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"创建归档时发生错误: {e}")
        logger.debug(f"错误输出: {e.stderr.decode() if e.stderr else 'None'}")
        return False
    except Exception as e:
        logger.error(f"创建归档时发生未知错误: {e}")
        return False


# 测试函数
if __name__ == "__main__":
    try:
        from modules.constants import setup_logger
    except ImportError as e:
        print(f"导入模块时出错: {e}")
        sys.exit(1)
    import tempfile
    
    # 设置日志
    logger = setup_logger(verbose=True)
    
    # 创建测试目录和文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试内容
        test_src_dir = os.path.join(temp_dir, "test_dir")
        os.makedirs(test_src_dir)
        
        with open(os.path.join(test_src_dir, "test.txt"), "w") as f:
            f.write("Test content")
        
        # 测试创建归档
        test_archive = os.path.join(temp_dir, "test.tar.gz")
        if create_archive(test_src_dir, test_archive):
            logger.info(f"创建归档成功: {test_archive}")
            
            # 测试解压归档
            extract_dir = os.path.join(temp_dir, "extract_test")
            if extract_archive(test_archive, extract_dir):
                logger.info(f"解压归档成功: {extract_dir}")
                
                # 验证解压结果
                extracted_file = os.path.join(extract_dir, "test_dir", "test.txt")
                if os.path.exists(extracted_file):
                    with open(extracted_file, "r") as f:
                        content = f.read()
                    logger.info(f"解压后文件内容: {content}")
                    logger.info("测试完成: 全部成功")
                else:
                    logger.error(f"解压后文件不存在: {extracted_file}")
            else:
                logger.error("解压测试失败")
        else:
            logger.error("创建归档测试失败")
