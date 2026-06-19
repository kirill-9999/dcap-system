#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safe OCR Worker - изолированный процесс для OCR
"""

import os
import sys
import json
import tempfile
import time
import base64

# Ключевое: ограничиваем потоки Tesseract ДО импорта
os.environ["OMP_THREAD_LIMIT"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import pytesseract
from PIL import Image, ImageEnhance


def ocr_image(image_data: bytes) -> str:
    """OCR одного изображения"""
    temp_file = None
    
    try:
        # Сохраняем изображение во временный файл
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(image_data)
            temp_file = f.name
        
        # Открываем и обрабатываем
        img = Image.open(temp_file)
        
        # Конвертируем в RGB если нужно
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Увеличение контраста
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        
        # OCR
        text = pytesseract.image_to_string(
            img,
            lang='rus+eng',
            config='--oem 1 --psm 6'
        )
        
        return text[:3000] if text else ""
        
    except Exception as e:
        return ""
    finally:
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except:
                pass


def main():
    """Точка входа для дочернего процесса"""
    if len(sys.argv) < 2:
        return
    
    # Получаем путь к файлу с данными
    data_file = sys.argv[1]
    
    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        image_data = base64.b64decode(data['image'])
        result = ocr_image(image_data)
        print(result)
        
    except Exception as e:
        print("")
    finally:
        # Удаляем временный файл
        try:
            if os.path.exists(data_file):
                os.unlink(data_file)
        except:
            pass


if __name__ == "__main__":
    main()