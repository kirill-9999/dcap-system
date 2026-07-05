#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze results of scanning E:\much_of_test_files
"""

import sys
import sqlite3
from pathlib import Path

# ========================================
# FIX: Добавляем корень проекта в PYTHONPATH
# ========================================
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def analyze():
    db_path = PROJECT_ROOT / "manager" / "src" / "db" / "dcap.db"
    state_file = PROJECT_ROOT / "state_large.json"
    
    if not db_path.exists():
        print("❌ Database not found")
        print(f"   Looking for: {db_path}")
        return
    
    print("=" * 70)
    print("📊 SCAN RESULTS ANALYSIS")
    print(f"   Source: E:\\much_of_test_files")
    print("=" * 70)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Общая статистика
    cursor.execute("SELECT COUNT(*) FROM findings")
    total_findings = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(DISTINCT file_path) FROM findings")
    unique_files = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM scan_tasks WHERE status = 'COMPLETED'")
    completed = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM scan_tasks WHERE status = 'FAILED'")
    failed = cursor.fetchone()[0] or 0
    
    print(f"\n📈 OVERALL STATISTICS:")
    print(f"   Total findings: {total_findings:,}")
    print(f"   Files with findings: {unique_files:,}")
    print(f"   Completed tasks: {completed}")
    print(f"   Failed tasks: {failed}")
    
    if state_file.exists():
        with open(state_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            processed = len(lines)
            print(f"   Processed files (state): {processed:,}")
    
    # Находки по категориям
    cursor.execute("""
        SELECT category, COUNT(*) 
        FROM findings 
        GROUP BY category 
        ORDER BY COUNT(*) DESC
    """)
    by_category = cursor.fetchall()
    
    if by_category:
        print(f"\n📂 FINDINGS BY CATEGORY:")
        for category, count in by_category:
            print(f"   {category}: {count:,}")
    
    # Находки по классификаторам
    cursor.execute("""
        SELECT classifier_name, COUNT(*) 
        FROM findings 
        GROUP BY classifier_name 
        ORDER BY COUNT(*) DESC
    """)
    by_classifier = cursor.fetchall()
    
    if by_classifier:
        print(f"\n🔍 FINDINGS BY CLASSIFIER:")
        for classifier, count in by_classifier:
            print(f"   {classifier}: {count:,}")
    
    # Топ файлов
    cursor.execute("""
        SELECT file_path, COUNT(*) as cnt 
        FROM findings 
        GROUP BY file_path 
        ORDER BY cnt DESC 
        LIMIT 10
    """)
    top_files = cursor.fetchall()
    
    if top_files:
        print(f"\n📄 TOP 10 FILES BY FINDINGS:")
        for file_path, count in top_files:
            name = Path(file_path).name
            print(f"   {name}: {count} findings")
    
    # Статистика по типам файлов
    cursor.execute("""
        SELECT 
            CASE 
                WHEN file_path LIKE '%.txt' THEN 'txt'
                WHEN file_path LIKE '%.pdf' THEN 'pdf'
                WHEN file_path LIKE '%.docx' THEN 'docx'
                WHEN file_path LIKE '%.xlsx' THEN 'xlsx'
                WHEN file_path LIKE '%.png' THEN 'png'
                WHEN file_path LIKE '%.jpg' THEN 'jpg'
                WHEN file_path LIKE '%.jpeg' THEN 'jpeg'
                WHEN file_path LIKE '%.json' THEN 'json'
                WHEN file_path LIKE '%.xml' THEN 'xml'
                WHEN file_path LIKE '%.html' THEN 'html'
                WHEN file_path LIKE '%.py' THEN 'py'
                WHEN file_path LIKE '%.js' THEN 'js'
                WHEN file_path LIKE '%.csv' THEN 'csv'
                WHEN file_path LIKE '%.log' THEN 'log'
                ELSE 'other'
            END as ext,
            COUNT(*) as count
        FROM findings
        GROUP BY ext
        ORDER BY count DESC
    """)
    by_ext = cursor.fetchall()
    
    if by_ext:
        print(f"\n📁 FINDINGS BY FILE TYPE:")
        for ext, count in by_ext:
            print(f"   .{ext}: {count:,}")
    
    # Ошибки
    cursor.execute("SELECT COUNT(*) FROM failed_files")
    failed_files = cursor.fetchone()[0] or 0
    
    if failed_files > 0:
        print(f"\n⚠️ FAILED FILES: {failed_files}")
        cursor.execute("""
            SELECT error_type, COUNT(*) 
            FROM failed_files 
            GROUP BY error_type
        """)
        for error_type, count in cursor.fetchall():
            print(f"   {error_type}: {count}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    
    # Итоговая оценка (только если есть данные)
    total_files = unique_files + failed_files
    if total_files > 0:
        print(f"📊 FINAL ASSESSMENT:")
        print(f"   Percentage of files with findings: {unique_files / total_files * 100:.1f}%")
        if unique_files > 0:
            print(f"   Average findings per file: {total_findings / unique_files:.2f}")
        else:
            print(f"   Average findings per file: 0")
    else:
        print("📊 FINAL ASSESSMENT:")
        print("   No data to analyze")
    
    print("=" * 70)

if __name__ == "__main__":
    analyze()