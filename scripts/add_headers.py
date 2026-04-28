#!/usr/bin/env python3
"""
批量添加文件头部和尾部注释

使用方法:
python add_headers.py [--header] [--footer] [--dry-run]
"""

import os
import argparse


def read_template(filepath):
    """读取模板文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def add_header(filepath, header):
    """给文件添加头部注释"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已存在头部
    if content.startswith(header[:50]):
        return False
    
    new_content = header + '\n' + content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


def add_footer(filepath, footer):
    """给文件添加尾部注释"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已存在尾部
    if footer[:30] in content:
        return False
    
    new_content = content.rstrip() + '\n' + footer + '\n'
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


def main():
    parser = argparse.ArgumentParser(description='批量添加文件头部和尾部注释')
    parser.add_argument('--header', action='store_true', help='添加头部注释')
    parser.add_argument('--footer', action='store_true', help='添加尾部注释')
    parser.add_argument('--dry-run', action='store_true', help='模拟运行，不实际修改文件')
    args = parser.parse_args()
    
    if not args.header and not args.footer:
        print("请指定 --header 或 --footer")
        return
    
    src_dir = 'src'
    header_template = read_template('HEADER_TEMPLATE') if args.header else None
    footer_template = read_template('FOOTER_TEMPLATE') if args.footer else None
    
    modified_count = 0
    skipped_count = 0
    
    for root, dirs, files in os.walk(src_dir):
        for filename in files:
            if filename.endswith('.py'):
                filepath = os.path.join(root, filename)
                
                if args.header and not args.dry_run:
                    if add_header(filepath, header_template):
                        modified_count += 1
                        print("[+] 添加头部: " + filepath)
                    else:
                        skipped_count += 1
                        print("[=] 已存在头部: " + filepath)
                
                if args.footer and not args.dry_run:
                    if add_footer(filepath, footer_template):
                        modified_count += 1
                        print("[+] 添加尾部: " + filepath)
                    else:
                        skipped_count += 1
                        print("[=] 已存在尾部: " + filepath)
    
    print("\n处理完成:")
    print("  修改文件: " + str(modified_count))
    print("  跳过文件: " + str(skipped_count))


if __name__ == '__main__':
    main()
