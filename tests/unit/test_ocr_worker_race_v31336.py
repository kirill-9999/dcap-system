"""Smoke-тесты BUG-137 (v3.13.36): гонка temp-файлов OCREngine при параллельном сканировании.

Корень: extract_document_text → DocumentExtractor создаёт новый OCREngine на
каждый файл с temp_dir=tempfile.gettempdir(); OCREngine.__init__ вызывал
_cleanup_temp_files(), удалявший ВСЕ tmp*/ocr_* в общем системном temp —
параллельные OCREngine стирали temp-файлы (входной .png и выходной .txt)
друг друга во время работы tesseract → PNG молча терял OCR-находки.

Фикс: у каждого OCREngine — своя уникальная подпапка _work_dir, все временные
файлы создаются и удаляются только в ней.

Если OCR недоступен в unit-окружении (нет Tesseract/Pillow) — тест skip
с явной причиной, воспроизведение на живом стенде (TASK-BUG137-4).
"""

import re
import sys
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNER_DIR = ROOT / "scanner"
for _p in (str(ROOT), str(SCANNER_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scanner.src.finding import Finding  # noqa: E402
from scanner.connectors.filesystem import FilesystemConnector  # noqa: E402


TESSERACT_CANDIDATES = [
    r"D:\dev\Tesseract-OCR\tesseract.exe",
    r"E:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _tesseract_available() -> bool:
    if shutil.which("tesseract"):
        return True
    return any(
        Path(p).exists()
        for p in TESSERACT_CANDIDATES
    )


def require_ocr():
    """Скип теста, если в окружении нет OCR-стека."""
    pytest.importorskip("PIL", reason="Нет Pillow — нельзя создать PNG")
    if not _tesseract_available():
        pytest.skip(
            "Tesseract не найден в unit-окружении — воспроизведение на живом стенде (TASK-BUG137-4)"
        )


OCR_TEXT = (
    "Phone: +7 912 345-67-89\n"
    "Email: user@example.com\n"
    "Passport: 0123 456789\n"
    "Name: John Doe"
)


def _make_png(path: Path) -> Path:
    """Создаёт PNG с PII-текстом (латиница, крупный шрифт для OCR)."""
    from PIL import Image, ImageDraw

    lines = OCR_TEXT.splitlines()
    img = Image.new("RGB", (620, 30 + 40 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black")
        y += 40
    img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
    path.write_bytes(_png_bytes(img))
    return path


def _png_bytes(img) -> bytes:
    """Сохранить изображение в PNG в памяти (PIL 8+)."""
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _RegexPiiClassifier:
    """Лёгкий классификатор без Presidio: ищем 4 PII-признака в тексте.

    Цель теста — не распознавание (Presidio), а OCR-тракт: извлечение текста
    из PNG и отсутствие потери находок при параллелизме. Поэтому классификатор
    максимально простой и без внешних моделей.
    """

    classifier_name = "regex_pii_test"

    def __init__(self):
        self._patterns = [
            (re.compile(r"\+7[\s\d-]+"), "phone"),
            (re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b"), "email"),
            (re.compile(r"\b\d{4}\s+\d{6}\b"), "passport"),
            (re.compile(r"Name:\s+([A-Za-z ]+)"), "person"),
        ]

    def file_prefilter(self, text: str) -> bool:
        return bool(text and ("Phone" in text or "Email" in text))

    def scan_text(self, text: str):
        findings = []
        for line_num, line in enumerate(text.splitlines(), 1):
            for pat, category in self._patterns:
                m = pat.search(line)
                if m:
                    findings.append(Finding(
                        line_number=line_num,
                        line_text=line,
                        match_text=m.group(1) if m.groups() else m.group(0),
                        start_pos=m.start(),
                        end_pos=m.end(),
                        finding_type="pii",
                        category=category,
                        severity="medium",
                        detector="regex",
                    ))
        return findings


class TestOcrRace:
    """BUG-137: OCR-находки не теряются при параллельном сканировании."""

    def _scan(self, connector: FilesystemConnector, classifiers, path: Path):
        return connector.scan_file(str(path), classifiers=classifiers)

    def test_single_png_gives_findings(self, tmp_path):
        """Одиночный прогон одного PNG — 4 находки (регресс D2/D4)."""
        require_ocr()
        png = _make_png(tmp_path / "single.png")
        connector = FilesystemConnector({"ocr_enabled": True})
        findings = self._scan(connector, [_RegexPiiClassifier()], png)
        assert len(findings) >= 4
        for f in findings:
            assert f.fragment_type == "image_region"
            assert f.detector == "ocr"

    def test_parallel_png_losses_none(self, tmp_path):
        """Параллельный прогон PNG + txt (8 потоков) — все PNG дают находки.

        До фикса параллельные OCREngine чистили общий системный temp и часть
        PNG получала 0 находок (тихая потеря). После фикса — каждый PNG
        даёт те же findings, что и одиночный прогон.
        """
        require_ocr()

        scan_dir = tmp_path / "corpus"
        scan_dir.mkdir()
        pngs = [_make_png(scan_dir / f"img_{i}.png") for i in range(4)]
        for i in range(7):
            (scan_dir / f"empty_{i}.txt").write_text("", encoding="utf-8")

        connector = FilesystemConnector({"ocr_enabled": True})
        classifiers = [_RegexPiiClassifier()]

        # Базовый одиночный прогон первого PNG — эталон
        baseline = len(self._scan(connector, classifiers, pngs[0]))
        assert baseline >= 4, f"эталонный PNG должен давать находки, получено {baseline}"

        def _scan_one(p: Path):
            return len(self._scan(connector, classifiers, p))

        with ThreadPoolExecutor(max_workers=8) as ex:
            per_file = list(ex.map(_scan_one, pngs + [] + list(scan_dir.glob("empty_*.txt"))))

        png_counts = per_file[:len(pngs)]
        for i, count in enumerate(png_counts):
            assert count >= 4, f"PNG img_{i} потерял OCR-находки: {count} (эталон {baseline})"

    def test_parallel_stable_three_runs(self, tmp_path):
        """Регресс на стабильность: 3 повтора параллельного прогона одинаковы."""
        require_ocr()

        scan_dir = tmp_path / "corpus"
        scan_dir.mkdir()
        pngs = [_make_png(scan_dir / f"img_{i}.png") for i in range(3)]
        for i in range(8):
            (scan_dir / f"empty_{i}.txt").write_text("", encoding="utf-8")

        connector = FilesystemConnector({"ocr_enabled": True})
        classifiers = [_RegexPiiClassifier()]

        def _scan_one(p: Path):
            return len(self._scan(connector, classifiers, p))

        totals = []
        for _ in range(3):
            with ThreadPoolExecutor(max_workers=8) as ex:
                counts = list(ex.map(_scan_one, pngs))
            totals.append(counts)
            assert all(c >= 4 for c in counts), f"PNG потерял находки: {counts}"

        assert totals[0] == totals[1] == totals[2], f"прогоны различаются: {totals}"