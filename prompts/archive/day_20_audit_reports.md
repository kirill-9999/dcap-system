📋 ТЗ: ОТЧЕТЫ ПО АУДИТУ (ДЕНЬ 20)
Файл: prompts/tz/day_20_audit_reports.md

🎯 ЦЕЛЬ
Создать систему отчетов по аудиту с возможностью экспорта в PDF и Excel. Пользователь должен иметь возможность:

Выбрать период и фильтры для отчета

Просмотреть сводку событий

Экспортировать отчет в PDF и Excel

Сохранять шаблоны отчетов (опционально)

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ
Изменить:
text
webui/main.py                 # Добавить страницу/модалку отчетов
webui/api/routes.py           # Добавить API для генерации отчетов
Добавить зависимости:
text
requirements.txt              # + openpyxl, reportlab (или fpdf)
📋 ДЕТАЛЬНОЕ ТЗ
1. Добавить зависимости
В корневой requirements.txt добавить:

text
openpyxl>=3.1.0      # для Excel-отчетов
reportlab>=4.0.0     # для PDF-отчетов
2. API для отчетов (webui/api/routes.py)
python
from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io

# ========== МОДЕЛИ ==========

class ReportFilter(BaseModel):
    days: int = 7
    event_type: Optional[str] = None
    user: Optional[str] = None
    file_path: Optional[str] = None
    agent_id: Optional[int] = None

# ========== API ==========

@router.post("/api/audit/report/preview")
def preview_audit_report(
    filter: ReportFilter,
    db: Session = Depends(get_db)
):
    """
    Предпросмотр данных для отчета
    """
    since = datetime.utcnow() - timedelta(days=filter.days)

    query = db.query(AuditLog).filter(AuditLog.created_at >= since)

    if filter.event_type:
        query = query.filter(AuditLog.event_type == filter.event_type)
    if filter.user:
        query = query.filter(AuditLog.user.ilike(f"%{filter.user}%"))
    if filter.file_path:
        query = query.filter(AuditLog.file_path.ilike(f"%{filter.file_path}%"))
    if filter.agent_id:
        query = query.filter(AuditLog.agent_id == filter.agent_id)

    total = query.count()

    # Статистика по типам
    from sqlalchemy import func
    type_stats = db.query(
        AuditLog.event_type,
        func.count(AuditLog.id).label('count')
    ).filter(AuditLog.created_at >= since)\
     .group_by(AuditLog.event_type).all()

    # Топ пользователей
    user_stats = db.query(
        AuditLog.user,
        func.count(AuditLog.id).label('count')
    ).filter(AuditLog.created_at >= since)\
     .filter(AuditLog.user.isnot(None))\
     .group_by(AuditLog.user)\
     .order_by(func.count(AuditLog.id).desc())\
     .limit(10).all()

    # Последние 100 событий для деталей
    events = query.order_by(AuditLog.created_at.desc()).limit(100).all()

    return {
        "total": total,
        "days": filter.days,
        "type_stats": [{"type": s[0], "count": s[1]} for s in type_stats],
        "top_users": [{"user": s[0], "count": s[1]} for s in user_stats],
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "user": e.user or "—",
                "file_path": e.file_path,
                "source_host": e.source_host or "—",
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
    }


@router.post("/api/audit/report/export/excel")
def export_audit_report_excel(
    filter: ReportFilter,
    db: Session = Depends(get_db)
):
    """
    Экспорт отчета в Excel
    """
    data = preview_audit_report(filter, db)

    wb = Workbook()

    # Лист 1: Сводка
    ws1 = wb.active
    ws1.title = "Сводка"
    ws1.append(["📊 Отчет по аудиту"])
    ws1.append([f"Период: {filter.days} дней"])
    ws1.append([f"Всего событий: {data['total']}"])
    ws1.append([])

    ws1.append(["Тип события", "Количество"])
    for stat in data["type_stats"]:
        ws1.append([stat["type"], stat["count"]])
    ws1.append([])

    ws1.append(["Топ пользователи"])
    ws1.append(["Пользователь", "Событий"])
    for user in data["top_users"]:
        ws1.append([user["user"], user["count"]])

    # Лист 2: Детали
    ws2 = wb.create_sheet("Детали")
    ws2.append(["ID", "Тип", "Пользователь", "Файл", "Источник", "Время"])
    for event in data["events"]:
        ws2.append([
            event["id"],
            event["event_type"],
            event["user"],
            event["file_path"],
            event["source_host"],
            event["created_at"]
        ])

    # Автоширина
    for ws in wb.worksheets:
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"audit_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/api/audit/report/export/pdf")
def export_audit_report_pdf(
    filter: ReportFilter,
    db: Session = Depends(get_db)
):
    """
    Экспорт отчета в PDF
    """
    data = preview_audit_report(filter, db)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # Заголовок
    story.append(Paragraph("📊 Отчет по аудиту", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Период: {filter.days} дней", styles['Normal']))
    story.append(Paragraph(f"Всего событий: {data['total']}", styles['Normal']))
    story.append(Spacer(1, 20))

    # Статистика по типам
    story.append(Paragraph("Типы событий", styles['Heading2']))
    table_data = [["Тип", "Количество"]]
    for stat in data["type_stats"]:
        table_data.append([stat["type"], str(stat["count"])])
    t = Table(table_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # Топ пользователи
    story.append(Paragraph("Топ пользователи", styles['Heading2']))
    table_data = [["Пользователь", "Событий"]]
    for user in data["top_users"]:
        table_data.append([user["user"], str(user["count"])])
    t = Table(table_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))

    # Детали (только 50 последних)
    story.append(Paragraph(f"Последние события (первые 50 из {len(data['events'])})", styles['Heading2']))
    table_data = [["Тип", "Пользователь", "Файл", "Время"]]
    for event in data["events"][:50]:
        table_data.append([
            event["event_type"],
            event["user"],
            event["file_path"][:50] + "..." if len(event["file_path"]) > 50 else event["file_path"],
            event["created_at"][:19] if event["created_at"] else "—"
        ])
    t = Table(table_data, colWidths=[60, 80, 200, 120])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    story.append(t)

    doc.build(story)
    buffer.seek(0)

    filename = f"audit_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
3. WebUI — страница отчетов (webui/main.py)
Добавить кнопку на странице аудита:

html
<!-- Кнопка "📊 Отчет" -->
<button id="open-report-modal" class="btn btn-primary" onclick="openReportModal()">
    📊 Отчет
</button>
Модальное окно отчета:

html
<!-- Модальное окно: Отчет -->
<div id="report-modal" class="modal" style="display:none;">
    <div class="modal-content" style="max-width:700px;">
        <h2>📊 Отчет по аудиту</h2>

        <div class="filter-card">
            <div class="filter-row">
                <div class="filter-group">
                    <label>📅 Период (дней):</label>
                    <select id="report-days" class="form-select">
                        <option value="1">1 день</option>
                        <option value="7" selected>7 дней</option>
                        <option value="30">30 дней</option>
                        <option value="90">90 дней</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label>📋 Тип события:</label>
                    <select id="report-type" class="form-select">
                        <option value="">Все типы</option>
                        <option value="read">📖 Чтение</option>
                        <option value="write">✏️ Запись</option>
                        <option value="delete">🗑️ Удаление</option>
                        <option value="move">📦 Перемещение</option>
                    </select>
                </div>
            </div>
            <div class="filter-row">
                <div class="filter-group">
                    <label>👤 Пользователь:</label>
                    <input type="text" id="report-user" placeholder="Введите имя..." class="form-input">
                </div>
                <div class="filter-group">
                    <label>📁 Файл/путь:</label>
                    <input type="text" id="report-path" placeholder="Поиск по пути..." class="form-input">
                </div>
            </div>
        </div>

        <!-- Предпросмотр -->
        <div id="report-preview" style="margin-top:16px;">
            <p>Загружаем данные...</p>
        </div>

        <div class="modal-actions" style="margin-top:20px; display:flex; gap:10px; justify-content:flex-end;">
            <button onclick="closeModal('report-modal')" class="btn btn-secondary">Закрыть</button>
            <button onclick="exportReport('excel')" class="btn btn-success">📊 Excel</button>
            <button onclick="exportReport('pdf')" class="btn btn-danger">📄 PDF</button>
        </div>
    </div>
</div>
4. JavaScript (webui/main.py)
javascript
// ==================== ОТЧЕТЫ ====================

let currentReportFilter = {};

async function openReportModal() {
    const modal = document.getElementById('report-modal');
    modal.style.display = 'block';

    // Загрузить предпросмотр
    await generateReportPreview();

    // Обработчики фильтров
    document.querySelectorAll('#report-days, #report-type, #report-user, #report-path').forEach(el => {
        el.onchange = generateReportPreview;
        el.oninput = generateReportPreview;
    });
}

async function generateReportPreview() {
    const filter = {
        days: parseInt(document.getElementById('report-days').value) || 7,
        event_type: document.getElementById('report-type').value || null,
        user: document.getElementById('report-user').value || null,
        file_path: document.getElementById('report-path').value || null
    };

    currentReportFilter = filter;

    try {
        const response = await fetch('/api/audit/report/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(filter)
        });
        const data = await response.json();

        renderReportPreview(data);
    } catch (e) {
        document.getElementById('report-preview').innerHTML = '<p style="color:red;">❌ Ошибка загрузки данных</p>';
    }
}

function renderReportPreview(data) {
    const container = document.getElementById('report-preview');

    let html = `
        <div class="report-stats" style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:16px;">
            <div class="stat-card"><span class="stat-value">${data.total}</span><span class="stat-label">Всего событий</span></div>
            <div class="stat-card"><span class="stat-value">${data.days}</span><span class="stat-label">Дней</span></div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
            <div>
                <h4>Типы событий</h4>
                <ul style="list-style:none; padding:0;">
                    ${data.type_stats.map(s => `<li>${s.type}: <strong>${s.count}</strong></li>`).join('') || '<li>Нет данных</li>'}
                </ul>
            </div>
            <div>
                <h4>Топ пользователи</h4>
                <ul style="list-style:none; padding:0;">
                    ${data.top_users.map(u => `<li>${u.user}: <strong>${u.count}</strong></li>`).join('') || '<li>Нет данных</li>'}
                </ul>
            </div>
        </div>
        <div style="margin-top:12px; font-size:0.9em; color:#6c757d;">
            Последние ${data.events.length} событий
        </div>
    `;
    container.innerHTML = html;
}

async function exportReport(format) {
    const filter = currentReportFilter;

    try {
        const response = await fetch(`/api/audit/report/export/${format}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(filter)
        });

        if (!response.ok) {
            throw new Error('Export failed');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = response.headers.get('Content-Disposition')?.split('filename=')[1] || `report.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('📊 Отчет экспортирован', 'success');
    } catch (e) {
        console.error('Export error:', e);
        showToast('Ошибка экспорта отчета', 'error');
    }
}
✅ КРИТЕРИИ ПРИЕМКИ
□ Добавлены зависимости openpyxl и reportlab
□ API /api/audit/report/preview возвращает сводку
□ API /api/audit/report/export/excel возвращает Excel-файл
□ API /api/audit/report/export/pdf возвращает PDF-файл
□ В WebUI есть кнопка «📊 Отчет» на странице аудита
□ Модальное окно отчета открывается с фильтрами
□ Предпросмотр показывает статистику
□ Экспорт Excel работает
□ Экспорт PDF работает
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
powershell
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить WebUI
python run_webui.py

# 3. Открыть http://localhost:8001 → страница «Аудит»
# 4. Нажать «📊 Отчет»
# 5. Выбрать фильтры → предпросмотр обновляется
# 6. Нажать «Excel» → скачивается .xlsx
# 7. Нажать «PDF» → скачивается .pdf
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
webui/
├── main.py                 # ✅ + кнопка отчета, модалка, JS
├── api/routes.py           # ✅ + API отчетов
└── requirements.txt        # ✅ + openpyxl, reportlab
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_20_audit_reports
git add webui/ requirements.txt
git commit -m "feat: День 20 — отчеты по аудиту (Excel, PDF)"
Разработчик (кодер), приступай! 🚀