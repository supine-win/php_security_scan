# PHP安全扫描器

这个Python脚本用于扫描PHP文件中可能存在的安全威胁或被篡改的迹象。支持一键安装和一键运行。

## 功能特点

- 递归扫描指定目录中的所有PHP文件
- 检测多种常见PHP安全漏洞和篡改特征：
  - 编码后的命令执行（如base64_decode后执行）
  - 命令注入（exec, system等接收用户输入）
  - 可疑的文件操作
  - 动态函数创建
  - SQL注入漏洞
  - 命令执行（通过反引号）
  - 代码执行（如preg_replace的/e修饰符）
  - 代码混淆（可疑的变量命名和赋值）
  - 恶意内容（如iframe插入）
  - 远程文件包含
  - 直接代码注入
  - 变量操作（如unsafe extract）
  - 不安全的文件上传
  - 可疑的隐藏输入
  - 文件头部注入
  - 大块编码数据
  - **编码内容输出**（如echo base64_decode形式的隐藏输出）
  - **多层编码链**（嵌套的编码/解码操作）
  - **可疑函数**（包含编码解码操作的自定义函数）
  - **间接编码输出**（变量赋值后输出的隐藏方式）
  - **远程代码执行组合**（eval+file_get_contents+base64_decode组合）
  - **错误隐藏与代码执行**（禁用错误显示后执行可疑代码）
- 将扫描结果输出到控制台和CSV文件
- 结果详细列出文件路径、行号、问题类型和问题代码内容

## 使用方法

### 一键运行

```bash
# 基本用法（默认只启用第一个特征）
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/php_scanner/run.sh | sh -s -- /path/to/php/directory

# 指定输出文件
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/php_scanner/run.sh | sh -s -- /path/to/php/directory -o output_results.csv

# 使用特定特征ID进行扫描（如1号、3号和5号特征）
curl -sSL https://raw.githubusercontent.com/supine-win/php_security_scan/main/php_scanner/run.sh | sh -s -- /path/to/php/directory -p 1,3,5
```

### 本地使用

下载后可以直接运行：

```bash
# 基本用法（交互式选择要检测的特征）
python main.py /path/to/php/directory

# 指定输出文件
python main.py /path/to/php/directory -o output_results.csv 

# 使用特定特征ID进行扫描
python main.py /path/to/php/directory -p 1,3,5

# 非交互模式，使用默认特征
python main.py /path/to/php/directory --non-interactive
```

## 交互式特征选择

运行脚本时，您可以选择要检测的PHP安全漏洞特征。默认情况下，只启用"编码后的命令执行"特征，以减少误报。

```
请选择要检测的PHP安全漏洞特征：
--------------------------------------------------
[X]  1. Encoded Command Execution - Potential execution of encoded/obfuscated code
[ ]  2. Command Injection - Direct execution of user-controlled input
[ ]  3. Suspicious File Operation - File operations with user input
...
--------------------------------------------------
请输入要选择的特征ID（用逗号分隔），直接回车使用默认选择，输入'all'选择全部：
> 1,3,5

已选择 3 个特征进行检测
  1. Encoded Command Execution
  3. Suspicious File Operation
  5. SQL Injection Vulnerability
```
