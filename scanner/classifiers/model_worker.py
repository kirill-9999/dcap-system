#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Model Worker - отдельный процесс для NLP моделей
"""

import os
import gc
import time
import sys
from queue import Empty
import multiprocessing as mp
from multiprocessing import Queue, Process
from typing import Dict, Tuple

# Отключаем телеметрию и предупреждения
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"

# Подавление предупреждений
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


class ModelWorker:
    def __init__(self, models_cache: str = "models", use_bert: bool = True):
        self.models_cache = models_cache
        self.use_bert = use_bert
        self._ner_pipeline = None
        self._natasha_ner = None
        self._natasha_segmenter = None
        self._models_loaded = False
        self._running = True
        self._request_count = 0
        
        if models_cache:
            os.environ['HF_HOME'] = models_cache
            os.environ['HF_HUB_CACHE'] = os.path.join(models_cache, 'hub')
            os.environ['TRANSFORMERS_CACHE'] = os.path.join(models_cache, 'transformers')
            for d in [models_cache, os.environ['HF_HUB_CACHE'], os.environ['TRANSFORMERS_CACHE']]:
                os.makedirs(d, exist_ok=True)
    
    def _load_models(self):
        """Загрузка моделей NLP"""
        if self._models_loaded:
            return
        
        print(f"[MODEL_WORKER] Загрузка моделей... (PID: {os.getpid()})")
        print(f"[MODEL_WORKER] Режим OFFLINE, BERT: {'ВКЛЮЧЁН' if self.use_bert else 'ОТКЛЮЧЁН'}")
        
        # Загрузка Natasha
        try:
            from natasha import Segmenter, NewsEmbedding, NewsNERTagger
            self._natasha_segmenter = Segmenter()
            emb = NewsEmbedding()
            self._natasha_ner = NewsNERTagger(emb)
            print(f"[MODEL_WORKER] ✅ Natasha загружена")
        except Exception as e:
            print(f"[MODEL_WORKER] ❌ Natasha error: {e}")
            self._natasha_ner = None
        
        # Загрузка BERT (если включен)
        if self.use_bert:
            try:
                from transformers import pipeline, AutoModelForTokenClassification, AutoTokenizer
                model_name = "dslim/bert-base-NER"
                
                print(f"[MODEL_WORKER] Загрузка BERT из локального кэша...")
                
                try:
                    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
                    model = AutoModelForTokenClassification.from_pretrained(model_name, local_files_only=True)
                    print(f"[MODEL_WORKER] BERT загружен из локального кэша")
                except Exception as e:
                    print(f"[MODEL_WORKER] Локальная BERT не найдена: {e}")
                    print(f"[MODEL_WORKER] Работаем только с Natasha")
                    self._ner_pipeline = None
                    self.use_bert = False
                    self._models_loaded = True
                    
                    # Отправляем сигнал о готовности даже без BERT
                    return
                
                self._ner_pipeline = pipeline(
                    "ner",
                    model=model,
                    tokenizer=tokenizer,
                    aggregation_strategy="simple",
                    device=-1  # CPU
                )
                print(f"[MODEL_WORKER] ✅ BERT модель загружена")
            except Exception as e:
                print(f"[MODEL_WORKER] ❌ BERT error: {e}")
                self._ner_pipeline = None
        else:
            print(f"[MODEL_WORKER] BERT отключён, работаем только с Natasha")
            self._ner_pipeline = None
        
        self._models_loaded = True
        
        # Вывод информации о памяти
        try:
            import psutil
            mem = psutil.Process().memory_info().rss / 1024 / 1024
            print(f"[MODEL_WORKER] Память после загрузки моделей: {mem:.0f} MB")
        except:
            pass
        
        print(f"[MODEL_WORKER] ✅ Модели загружены, готов к работе")
    
    def _process_text(self, text: str) -> Dict:
        """Обработка текста: поиск имен и локаций"""
        result = {"persons": [], "locations": []}
        
        if not text or len(text.strip()) < 10:
            return result
        
        # Natasha NER
        if self._natasha_ner and self._natasha_segmenter:
            try:
                from natasha import Doc
                doc = Doc(text[:10000])
                doc.segment(self._natasha_segmenter)
                doc.tag_ner(self._natasha_ner)
                
                for span in doc.spans:
                    if span.type == 'PER':
                        # Проверка на дубликаты
                        if not any(p[0] == span.text for p in result["persons"]):
                            result["persons"].append((span.text, "natasha", 0.9))
                    elif span.type == 'LOC':
                        if not any(l[0] == span.text for l in result["locations"]):
                            result["locations"].append((span.text, "natasha", 0.85))
            except Exception as e:
                print(f"[MODEL_WORKER] Natasha error: {e}")
        
        # BERT NER
        if self._ner_pipeline:
            try:
                entities = self._ner_pipeline(text[:5000])
                for entity in entities:
                    entity_type = entity.get('entity_group', '')
                    word = entity.get('word', '').strip().replace('##', '')
                    confidence = entity.get('score', 0.7)
                    
                    if len(word) < 2:
                        continue
                    
                    if 'PER' in entity_type:
                        if not any(p[0] == word for p in result["persons"]):
                            result["persons"].append((word, "bert", confidence))
                    elif 'LOC' in entity_type:
                        if not any(l[0] == word for l in result["locations"]):
                            result["locations"].append((word, "bert", confidence))
            except Exception as e:
                print(f"[MODEL_WORKER] BERT error: {e}")
        
        # Ограничиваем количество результатов
        result["persons"] = result["persons"][:50]
        result["locations"] = result["locations"][:50]
        
        return result
    
    def _cleanup_temp_files(self):
        """Очистка временных файлов"""
        import tempfile
        from pathlib import Path
        
        temp_dir = Path(tempfile.gettempdir())
        try:
            for f in temp_dir.glob("tmp*"):
                try:
                    if f.is_file() and time.time() - f.stat().st_mtime > 3600:
                        f.unlink()
                except:
                    pass
        except:
            pass
    
    def run(self, request_queue: Queue, response_queue: Queue):
        """Основной цикл обработки"""
        print(f"[MODEL_WORKER] Процесс запущен (PID: {os.getpid()})")
        
        # Загрузка моделей
        self._load_models()
        
        # Отправляем сигнал о готовности
        try:
            response_queue.put({"id": 0, "ready": True})
            print(f"[MODEL_WORKER] Сигнал готовности отправлен")
        except Exception as e:
            print(f"[MODEL_WORKER] Не удалось отправить сигнал готовности: {e}")
        
        last_gc = time.time()
        last_cleanup = time.time()
        
        while self._running:
            try:
                try:
                    request = request_queue.get(timeout=1.0)
                except Empty:
                    # Периодическая очистка
                    now = time.time()
                    if now - last_gc > 60:
                        gc.collect()
                        last_gc = now
                    if now - last_cleanup > 300:
                        self._cleanup_temp_files()
                        last_cleanup = now
                    continue
                
                # Сигнал остановки
                if request is None:
                    break
                
                message_id = request.get("id", 0)
                text = request.get("text", "")
                
                # Обработка текста
                result = self._process_text(text)
                
                # Отправка ответа
                response_queue.put({
                    "id": message_id,
                    "result": result,
                    "success": True
                })
                
                self._request_count += 1
                
                # Периодический GC
                if self._request_count % 100 == 0:
                    gc.collect()
                    last_gc = time.time()
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[MODEL_WORKER] Error: {e}")
                if 'request' in locals():
                    try:
                        response_queue.put({
                            "id": request.get("id", 0),
                            "result": {"persons": [], "locations": []},
                            "success": False,
                            "error": str(e)
                        })
                    except:
                        pass
        
        print(f"[MODEL_WORKER] Завершение. Обработано запросов: {self._request_count}")
    
    def stop(self):
        self._running = True


def start_model_worker(models_cache: str = "models", use_bert: bool = True) -> Tuple[Process, Queue, Queue]:
    """Запуск ModelWorker в отдельном процессе"""
    try:
        mp.set_start_method('spawn', force=True)
    except RuntimeError:
        pass
    
    request_queue = Queue(maxsize=1000)
    response_queue = Queue(maxsize=1000)
    
    worker = ModelWorker(models_cache, use_bert)
    process = Process(
        target=worker.run,
        args=(request_queue, response_queue),
        name="ModelWorker",
        daemon=False
    )
    process.start()
    
    return process, request_queue, response_queue


def stop_model_worker(process: Process, request_queue: Queue, response_queue: Queue):
    """Остановка ModelWorker"""
    try:
        request_queue.put(None, timeout=1)
    except:
        pass
    
    if process and process.is_alive():
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            process.kill()


__all__ = ['start_model_worker', 'stop_model_worker', 'ModelWorker']