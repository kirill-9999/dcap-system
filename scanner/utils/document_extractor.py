#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DCAP Agent - Document Extractor with OCR Pool
"""

import os
import uuid
import zipfile
import io
import subprocess
import time
import warnings
import logging
from pathlib import Path
from typing import Optional, List, Tuple

# Отключаем предупреждения pypdf (warnings + логгер: "Multiple definitions in dictionary")
warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
logging.getLogger("pypdf").setLevel(logging.ERROR)

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import fitz
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    from openpyxl import load_workbook
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

try:
    import xlrd
    XLS_AVAILABLE = True
except ImportError:
    XLS_AVAILABLE = False

from utils.ocr_engine import OCREngine


class DocumentExtractor:
    """Извлечение текста и изображений из документов с OCREngine"""
    
    def __init__(self, temp_dir: Path, ocr_enabled: bool = True, max_ocr_workers: int = 2):
        self.temp_dir = Path(temp_dir) if isinstance(temp_dir, str) else temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.ocr_enabled = ocr_enabled and OCR_AVAILABLE
        self.ocr_count = 0
        self.ocr_errors = 0
        self.ocr_time = 0.0
        
        if self.ocr_enabled:
            self._ocr_engine = OCREngine(self.temp_dir, max_workers=max_ocr_workers, max_cache_size=500)
        else:
            self._ocr_engine = None
    
    def reset_ocr_engine(self):
        if self._ocr_engine:
            self._ocr_engine.reset()
    
    def reset_ocr_stats(self) -> None:
        self.ocr_count = 0
        self.ocr_errors = 0
        self.ocr_time = 0.0
    
    def get_ocr_stats(self) -> dict:
        if self._ocr_engine:
            return self._ocr_engine.get_stats()
        return {}
    
    def _ocr_image(self, image_data: bytes, filename: str = "image") -> Optional[str]:
        if not self.ocr_enabled or not self._ocr_engine:
            return None
        
        start = time.time()
        text = self._ocr_engine.ocr_image(image_data, timeout=60)
        elapsed = time.time() - start
        
        if text:
            self.ocr_count += 1
            self.ocr_time += elapsed
            return text
        
        self.ocr_errors += 1
        return None
    
    def _extract_images_from_zip(self, zip_data: bytes, media_prefix: str) -> List[str]:
        """Извлечение изображений из ZIP-архива (DOCX, XLSX) и OCR"""
        texts = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data), 'r') as zf:
                for file_info in zf.filelist:
                    if file_info.filename.startswith(media_prefix) and \
                       any(file_info.filename.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']):
                        try:
                            image_data = zf.read(file_info.filename)
                            text = self._ocr_image(image_data, file_info.filename)
                            if text:
                                texts.append(f"[Изображение: {text}]")
                        except:
                            pass
        except:
            pass
        return texts
    
    def extract_pdf(self, file_bytes: bytes, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Извлечение текста из PDF (сначала текст, потом OCR изображений)
        Returns:
            (text, error): если успешно -> (текст, None), если ошибка -> (None, сообщение_об_ошибке)
        """
        text_parts = []
        
        # 1. Пробуем извлечь текст через pypdf
        if PDF_AVAILABLE:
            try:
                reader = PdfReader(io.BytesIO(file_bytes))
                for page_num, page in enumerate(reader.pages[:50]):
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_parts.append(f"[Страница {page_num + 1}]\n{page_text}")
            except Exception as e:
                pass
        
        extracted_text = '\n'.join(text_parts).strip()
        
        # 2. Если текста нет или очень мало, пробуем OCR изображений через fitz
        if (not extracted_text or len(extracted_text) < 50) and self.ocr_enabled and FITZ_AVAILABLE:
            ocr_parts = []
            
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                
                for page_num, page in enumerate(doc):
                    # Получаем изображения со страницы
                    image_list = page.get_images(full=True)
                    
                    for img_index, img in enumerate(image_list[:15]):  # до 15 изображений на страницу
                        try:
                            xref = img[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            
                            # OCR изображения
                            ocr_text = self._ocr_image(image_bytes, f"{filename}_p{page_num + 1}_i{img_index + 1}")
                            if ocr_text and ocr_text.strip():
                                ocr_parts.append(f"[Изображение стр.{page_num + 1}: {ocr_text}]")
                        except:
                            pass
                
                doc.close()
                
                if ocr_parts:
                    ocr_result = '\n'.join(ocr_parts).strip()
                    if ocr_result:
                        return (ocr_result, None)
                    
            except Exception as e:
                pass
        
        # 3. Возвращаем то, что нашли
        if extracted_text:
            return (extracted_text, None)
        else:
            if self.ocr_enabled and FITZ_AVAILABLE:
                return (None, "PDF: текст не извлечён (файл содержит только изображения, но OCR не сработал)")
            else:
                return (None, "PDF: текст не извлечён (OCR отключён или PyMuPDF не установлен)")
    
    def extract_docx(self, file_bytes: bytes, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Извлечение текста из DOCX.
        Returns:
            (text, error): если успешно -> (текст, None), если ошибка -> (None, сообщение_об_ошибке)
        """
        if not DOCX_AVAILABLE:
            return None, "python-docx не установлен"
        
        text_parts = []
        temp_file = None
        
        try:
            temp_file = self.temp_dir / f"temp_{uuid.uuid4().hex}.docx"
            with open(temp_file, 'wb') as f:
                f.write(file_bytes)
            
            # Проверяем, что файл действительно DOCX
            if not zipfile.is_zipfile(temp_file):
                return None, "Файл не является ZIP-архивом (не DOCX)"
            
            doc = Document(temp_file)
            
            for para in doc.paragraphs:
                if para.text:
                    text_parts.append(para.text)
            
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if cell.text:
                            text_parts.append(cell.text)
            
            doc = None
            import gc
            gc.collect()
            
            extracted_text = '\n'.join(text_parts).strip()
            
            # Если текста нет, пробуем OCR изображений
            if not extracted_text and self.ocr_enabled:
                with open(temp_file, 'rb') as f:
                    zip_data = f.read()
                images_text = self._extract_images_from_zip(zip_data, 'word/media/')
                if images_text:
                    result = '\n'.join(images_text).strip()
                    if result:
                        # Удаляем временный файл
                        for _ in range(5):
                            try:
                                if temp_file and temp_file.exists():
                                    temp_file.unlink()
                                break
                            except PermissionError:
                                time.sleep(0.5)
                        return (result, None)
            
            # Удаляем временный файл
            for _ in range(5):
                try:
                    if temp_file and temp_file.exists():
                        temp_file.unlink()
                    break
                except PermissionError:
                    time.sleep(0.5)
            
            if extracted_text:
                return (extracted_text, None)
            else:
                return (None, "Текст не извлечён (возможно, файл пуст или содержит только изображения)")
            
        except zipfile.BadZipFile:
            return None, "Файл повреждён или не является DOCX (BadZipFile)"
        except Exception as e:
            return None, f"Ошибка при обработке DOCX: {str(e)[:200]}"
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
    def extract_xlsx(self, file_bytes: bytes, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Извлечение текста из XLSX.
        Returns:
            (text, error): если успешно -> (текст, None), если ошибка -> (None, сообщение_об_ошибке)
        """
        if not XLSX_AVAILABLE:
            return None, "openpyxl не установлен"
        
        text_parts = []
        temp_file = None
        
        try:
            temp_file = self.temp_dir / f"temp_{uuid.uuid4().hex}.xlsx"
            with open(temp_file, 'wb') as f:
                f.write(file_bytes)
            
            # Проверяем, что файл действительно XLSX
            if not zipfile.is_zipfile(temp_file):
                return None, "Файл не является ZIP-архивом (не XLSX)"
            
            wb = openpyxl.load_workbook(temp_file, data_only=True, read_only=True)
            
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                for row in sheet.iter_rows():
                    for cell in row:
                        if cell.value is not None:
                            text_parts.append(str(cell.value))
            
            wb.close()
            wb = None
            
            extracted_text = '\n'.join(text_parts).strip()
            
            # Если текста нет, пробуем OCR изображений
            if not extracted_text and self.ocr_enabled:
                with open(temp_file, 'rb') as f:
                    zip_data = f.read()
                images_text = self._extract_images_from_zip(zip_data, 'xl/media/')
                if images_text:
                    result = '\n'.join(images_text).strip()
                    if result:
                        # Удаляем временный файл
                        import gc
                        gc.collect()
                        for _ in range(5):
                            try:
                                if temp_file and temp_file.exists():
                                    temp_file.unlink()
                                break
                            except PermissionError:
                                time.sleep(0.5)
                        return (result, None)
            
            # Удаляем временный файл
            import gc
            gc.collect()
            for _ in range(5):
                try:
                    if temp_file and temp_file.exists():
                        temp_file.unlink()
                    break
                except PermissionError:
                    time.sleep(0.5)
            
            if extracted_text:
                return (extracted_text, None)
            else:
                return (None, "Текст не извлечён (возможно, файл пуст или содержит только изображения)")
            
        except zipfile.BadZipFile:
            return None, "Файл повреждён или не является XLSX (BadZipFile)"
        except Exception as e:
            return None, f"Ошибка при обработке XLSX: {str(e)[:200]}"
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
    def extract_xls(self, file_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
        """
        Извлечение текста из XLS (старый формат).
        Returns:
            (text, error): если успешно -> (текст, None), если ошибка -> (None, сообщение_об_ошибке)
        """
        if not XLS_AVAILABLE:
            return None, "xlrd не установлен"
        
        text_parts = []
        temp_file = None
        
        try:
            temp_file = self.temp_dir / f"temp_{uuid.uuid4().hex}.xls"
            with open(temp_file, 'wb') as f:
                f.write(file_bytes)
            
            wb = xlrd.open_workbook(str(temp_file))
            for sheet in wb.sheets():
                for row in range(sheet.nrows):
                    for col in range(sheet.ncols):
                        cell_value = sheet.cell_value(row, col)
                        if cell_value:
                            text_parts.append(str(cell_value))
            
            wb = None
            import gc
            gc.collect()
            
            for _ in range(5):
                try:
                    if temp_file and temp_file.exists():
                        temp_file.unlink()
                    break
                except PermissionError:
                    time.sleep(0.5)
            
            result_text = '\n'.join(text_parts)
            if result_text:
                return (result_text, None)
            else:
                return (None, "Текст не извлечён (возможно, файл пуст)")
            
        except xlrd.XLRDError as e:
            return None, f"Ошибка чтения XLS: {str(e)[:200]}"
        except Exception as e:
            return None, f"Ошибка при обработке XLS: {str(e)[:200]}"
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
    def extract_doc(self, file_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
        """
        Извлечение текста из DOC (старый формат) через catdoc.
        Returns:
            (text, error): если успешно -> (текст, None), если ошибка -> (None, сообщение_об_ошибке)
        """
        temp_file = None
        
        try:
            temp_file = self.temp_dir / f"temp_{uuid.uuid4().hex}.doc"
            with open(temp_file, 'wb') as f:
                f.write(file_bytes)
            
            result = subprocess.run(['catdoc', str(temp_file)], capture_output=True, text=True, timeout=30)
            
            for _ in range(5):
                try:
                    if temp_file and temp_file.exists():
                        temp_file.unlink()
                    break
                except PermissionError:
                    time.sleep(0.5)
            
            if result.returncode == 0 and result.stdout:
                return (result.stdout, None)
            elif result.returncode != 0:
                return (None, f"catdoc завершился с кодом {result.returncode}")
            else:
                return (None, "Текст не извлечён (файл пуст)")
            
        except FileNotFoundError:
            return (None, "catdoc не найден (установите catdoc или используйте другой формат)")
        except subprocess.TimeoutExpired:
            return (None, "catdoc timeout (30 сек)")
        except Exception as e:
            return (None, f"Ошибка при обработке DOC: {str(e)[:200]}")
        finally:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
    
    def extract_image(self, file_bytes: bytes, filename: str) -> Optional[str]:
        return self._ocr_image(file_bytes, filename)
    
    def extract_text(self, file_bytes: bytes, ext: str, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Извлечение текста из файла.
        Returns:
            (text, error): если успешно -> (текст, None), если ошибка -> (None, сообщение_об_ошибке)
        """
        if ext in ['txt', 'csv', 'log', 'json', 'md', 'ini', 'cfg', 'conf', 'yaml', 'yml', 'xml', 'html']:
            try:
                return (file_bytes.decode('utf-8')[:5000], None)
            except UnicodeDecodeError:
                try:
                    return (file_bytes.decode('cp1251')[:5000], None)
                except Exception as e:
                    return (None, f"Ошибка декодирования текста: {str(e)[:200]}")
        
        elif ext == 'pdf':
            return self.extract_pdf(file_bytes, filename)
        
        elif ext == 'docx':
            return self.extract_docx(file_bytes, filename)
        
        elif ext == 'doc':
            return self.extract_doc(file_bytes)
        
        elif ext == 'xlsx':
            return self.extract_xlsx(file_bytes, filename)
        
        elif ext == 'xls':
            return self.extract_xls(file_bytes)
        
        elif ext in ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp']:
            result = self.extract_image(file_bytes, filename)
            if result:
                return (result, None)
            else:
                return (None, f"Изображение: текст не распознан OCR (возможно, Tesseract не установлен или нет русского языка)")
        
        return (None, f"Неподдерживаемое расширение: {ext}")


__all__ = ['DocumentExtractor']