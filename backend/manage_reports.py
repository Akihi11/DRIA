#!/usr/bin/env python3
"""
报表管理工具
用于管理不同类型的报表文件，支持分类、移动、清理等操作
"""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import argparse
import json

# 添加项目根目录到路径
import sys
sys.path.append(str(Path(__file__).parent))

from backend.config import settings

class ReportManager:
    """报表管理器"""
    
    def __init__(self):
        self.base_dir = settings.REPORT_OUTPUT_DIR
        self.subdirs = settings.REPORT_SUBDIRS
        
    def list_reports(self, report_type: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """列出所有报表或指定类型的报表"""
        reports = {}
        
        # 如果指定了类型，只处理该类型
        if report_type and report_type in self.subdirs:
            types_to_process = [report_type]
        else:
            types_to_process = list(self.subdirs.keys())
        
        for rtype in types_to_process:
            subdir = self.base_dir / self.subdirs[rtype]
            if not subdir.exists():
                reports[rtype] = []
                continue
                
            report_files = []
            for file_path in subdir.glob("*.xlsx"):
                stat = file_path.stat()
                report_files.append({
                    "filename": file_path.name,
                    "full_path": str(file_path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size_mb": round(stat.st_size / 1024 / 1024, 2)
                })
            
            # 按修改时间排序
            report_files.sort(key=lambda x: x["modified"], reverse=True)
            reports[rtype] = report_files
        
        return reports
    
    def move_report(self, filename: str, from_type: str, to_type: str) -> bool:
        """移动报表到不同的分类"""
        if from_type not in self.subdirs or to_type not in self.subdirs:
            print(f"❌ 无效的报表类型: {from_type} 或 {to_type}")
            return False
        
        from_path = self.base_dir / self.subdirs[from_type] / filename
        to_path = self.base_dir / self.subdirs[to_type] / filename
        
        if not from_path.exists():
            print(f"❌ 源文件不存在: {from_path}")
            return False
        
        if to_path.exists():
            print(f"⚠️  目标文件已存在: {to_path}")
            response = input("是否覆盖? (y/N): ")
            if response.lower() != 'y':
                return False
        
        try:
            # 确保目标目录存在
            to_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(from_path), str(to_path))
            print(f"✅ 报表已移动: {filename} ({from_type} -> {to_type})")
            return True
        except Exception as e:
            print(f"❌ 移动失败: {e}")
            return False
    
    def copy_report(self, filename: str, from_type: str, to_type: str, new_name: str = None) -> bool:
        """复制报表到不同的分类"""
        if from_type not in self.subdirs or to_type not in self.subdirs:
            print(f"❌ 无效的报表类型: {from_type} 或 {to_type}")
            return False
        
        from_path = self.base_dir / self.subdirs[from_type] / filename
        target_filename = new_name if new_name else filename
        to_path = self.base_dir / self.subdirs[to_type] / target_filename
        
        if not from_path.exists():
            print(f"❌ 源文件不存在: {from_path}")
            return False
        
        if to_path.exists():
            print(f"⚠️  目标文件已存在: {to_path}")
            response = input("是否覆盖? (y/N): ")
            if response.lower() != 'y':
                return False
        
        try:
            # 确保目标目录存在
            to_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(from_path), str(to_path))
            print(f"✅ 报表已复制: {filename} -> {target_filename} ({from_type} -> {to_type})")
            return True
        except Exception as e:
            print(f"❌ 复制失败: {e}")
            return False
    
    def delete_report(self, filename: str, report_type: str, confirm: bool = True) -> bool:
        """删除报表"""
        if report_type not in self.subdirs:
            print(f"❌ 无效的报表类型: {report_type}")
            return False
        
        file_path = self.base_dir / self.subdirs[report_type] / filename
        
        if not file_path.exists():
            print(f"❌ 文件不存在: {file_path}")
            return False
        
        if confirm:
            print(f"⚠️  确认删除报表: {filename} ({report_type})")
            response = input("确认删除? (y/N): ")
            if response.lower() != 'y':
                print("取消删除")
                return False
        
        try:
            file_path.unlink()
            print(f"✅ 报表已删除: {filename}")
            return True
        except Exception as e:
            print(f"❌ 删除失败: {e}")
            return False
    
    def clean_empty_dirs(self):
        """清理空目录"""
        cleaned = 0
        for rtype, dirname in self.subdirs.items():
            subdir = self.base_dir / dirname
            if subdir.exists() and not any(subdir.iterdir()):
                try:
                    subdir.rmdir()
                    print(f"✅ 已清理空目录: {dirname}")
                    cleaned += 1
                except Exception as e:
                    print(f"⚠️  无法删除目录 {dirname}: {e}")
        
        if cleaned == 0:
            print("✅ 没有空目录需要清理")
        
        return cleaned
    
    def archive_old_reports(self, days: int = 30):
        """归档旧报表"""
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        archived_count = 0
        
        # 遍历除了archived之外的所有目录
        for rtype, dirname in self.subdirs.items():
            if rtype == "archived":
                continue
                
            subdir = self.base_dir / dirname
            if not subdir.exists():
                continue
            
            for file_path in subdir.glob("*.xlsx"):
                stat = file_path.stat()
                file_date = datetime.fromtimestamp(stat.st_mtime)
                
                if file_date < cutoff_date:
                    # 移动到archived目录
                    archived_dir = self.base_dir / self.subdirs["archived"]
                    archived_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 添加日期前缀避免冲突
                    archived_name = f"{file_date.strftime('%Y%m%d')}_{file_path.name}"
                    archived_path = archived_dir / archived_name
                    
                    try:
                        shutil.move(str(file_path), str(archived_path))
                        print(f"📦 已归档: {file_path.name} -> {archived_name}")
                        archived_count += 1
                    except Exception as e:
                        print(f"❌ 归档失败 {file_path.name}: {e}")
        
        print(f"✅ 共归档 {archived_count} 个报表")
        return archived_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取报表统计信息"""
        stats = {
            "total_reports": 0,
            "total_size_mb": 0,
            "by_type": {}
        }
        
        for rtype, dirname in self.subdirs.items():
            subdir = self.base_dir / dirname
            if not subdir.exists():
                stats["by_type"][rtype] = {"count": 0, "size_mb": 0}
                continue
            
            count = 0
            size_bytes = 0
            
            for file_path in subdir.glob("*.xlsx"):
                count += 1
                size_bytes += file_path.stat().st_size
            
            size_mb = round(size_bytes / 1024 / 1024, 2)
            stats["by_type"][rtype] = {
                "count": count,
                "size_mb": size_mb
            }
            
            stats["total_reports"] += count
            stats["total_size_mb"] += size_mb
        
        stats["total_size_mb"] = round(stats["total_size_mb"], 2)
        return stats

def print_reports_table(reports: Dict[str, List[Dict[str, Any]]]):
    """打印报表表格"""
    for rtype, file_list in reports.items():
        print(f"\n📁 {rtype} ({len(file_list)} 个文件)")
        print("-" * 80)
        
        if not file_list:
            print("   (空)")
            continue
        
        print(f"{'文件名':<40} {'大小(MB)':<10} {'修改时间':<20}")
        print("-" * 80)
        
        for file_info in file_list:
            print(f"{file_info['filename']:<40} {file_info['size_mb']:<10} {file_info['modified'][:19]:<20}")

def main():
    parser = argparse.ArgumentParser(description="报表管理工具")
    parser.add_argument("command", choices=["list", "move", "copy", "delete", "clean", "archive", "stats"], 
                       help="操作命令")
    parser.add_argument("--type", help="报表类型")
    parser.add_argument("--filename", help="文件名")
    parser.add_argument("--from-type", help="源类型")
    parser.add_argument("--to-type", help="目标类型")
    parser.add_argument("--new-name", help="新文件名")
    parser.add_argument("--days", type=int, default=30, help="归档天数")
    parser.add_argument("--yes", "-y", action="store_true", help="自动确认")
    
    args = parser.parse_args()
    
    manager = ReportManager()
    
    if args.command == "list":
        reports = manager.list_reports(args.type)
        print_reports_table(reports)
    
    elif args.command == "move":
        if not all([args.filename, args.from_type, args.to_type]):
            print("❌ 移动操作需要 --filename, --from-type, --to-type 参数")
            return
        manager.move_report(args.filename, args.from_type, args.to_type)
    
    elif args.command == "copy":
        if not all([args.filename, args.from_type, args.to_type]):
            print("❌ 复制操作需要 --filename, --from-type, --to-type 参数")
            return
        manager.copy_report(args.filename, args.from_type, args.to_type, args.new_name)
    
    elif args.command == "delete":
        if not all([args.filename, args.type]):
            print("❌ 删除操作需要 --filename, --type 参数")
            return
        manager.delete_report(args.filename, args.type, not args.yes)
    
    elif args.command == "clean":
        manager.clean_empty_dirs()
    
    elif args.command == "archive":
        manager.archive_old_reports(args.days)
    
    elif args.command == "stats":
        stats = manager.get_statistics()
        print("📊 报表统计信息")
        print("=" * 50)
        print(f"总报表数: {stats['total_reports']}")
        print(f"总大小: {stats['total_size_mb']} MB")
        print("\n按类型统计:")
        for rtype, type_stats in stats["by_type"].items():
            print(f"  {rtype}: {type_stats['count']} 个文件, {type_stats['size_mb']} MB")

if __name__ == "__main__":
    main()
