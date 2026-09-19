3. ROADMAP.md (обновлённый)
markdown
# 🗺️ ROADMAP.md — План развития и бэклог DCAP

**Обновлено:** 19.09.2026 (вечер)
**Стратегия:** Windows First → Linux → S3/MinIO → Enterprise Ready → Rust + DLP

---

## 🚀 Вехи

| Версия | Статус | Ключевые фичи |
|--------|--------|---------------|
| v1.0.0-v2.1.0 | ✅ | Обнаружение, классификация, WebUI, Linux-агент |
| **v3.0.0** | **🔄 Fix-спринт** | S3, AD, mTLS, архивация, Secret Scanner, Findings Refactor, админ-руководство, GitHub |
| v3.1.0 | 📋 | Rust Scanner, DLP/ICAP, SMB, Webhook, облака |
| v4.0.0 | 📋 | ML-классификаторы, Zero-Trust, SIEM |

---

## 📋 v3.0.0 — ENTERPRISE READY (🔄 ФИНАЛИЗАЦИЯ)

### День 45 — Fix-спринт (по итогам Блока 2)

**См. `TZ_FIX_SPRINT.md`.** Порядок:

1. **BUG-039** — `verify_token(expected_type)` (критично)
2. **BUG-046** — RBAC на `DELETE /api/resources` (критично)
3. **BUG-047** — RBAC на `DELETE /api/tasks` + транзакция (критично)
4. **BUG-048** — RBAC на `DELETE /api/scanner` + 500 (критично)
5. **BUG-049…055** — RBAC на остальные write-эндпоинты (важно)
6. **BUG-037** — `group_mapping` ед.ч. → мн.ч. (важно)
7. **BUG-043** — `catalog/tree` (важно)
8. **BUG-045** — `/api/scanner/*` 500 (важно)
9. **BUG-057** — Scanner fail-fast без ключей (важно)
10. **BUG-058** — Manager fallback `line_text_encrypted` (средне)
11. **BUG-059** — `tasks/create` регистр `type` (важно)
12. **BUG-038, 041, 042, 044** — средние
13. **TEST-NOTE** — документация

### Дни 42.1-42.4 — Админ-руководство ✅

### Дни 43-44 — Блок 1 + AD ✅

### День 45+ — Повторное тестирование RBAC (после фиксов)

### День 46 — Релиз v3.0.0

### Бэклог v3.0.0 (обновлённый)

| ID | Название | Приоритет | Статус |
|----|----------|-----------|--------|
| **BUG-039** | Refresh как access | 🔴🔴 | 📋 fix |
| **BUG-046** | DELETE resources без RBAC | 🔴🔴 | 📋 fix |
| **BUG-047** | DELETE tasks без auth | 🔴🔴 | 📋 fix |
| **BUG-048** | DELETE scanner без auth + 500 | 🔴🔴 | 📋 fix |
| BUG-037 | `group_mapping` ед.ч./мн.ч. | 🔴 | 📋 fix |
| BUG-043 | `catalog/tree` 500 | 🔴 | 📋 fix |
| BUG-045 | `/api/scanner/*` 500 | 🔴 | 📋 fix |
| BUG-049-055 | 7 unprotected write | 🔴 | 📋 fix |
| BUG-057 | Scanner legacy by default | 🔴 | 📋 fix |
| BUG-059 | `tasks/create` 500 | 🔴 | 📋 fix |
| BUG-038 | TTL не в env | 🟡 | 📋 |
| BUG-041 | Reuse refresh | 🟡 | 📋 |
| BUG-042 | `secure=False` hardcoded | 🟡 | 📋 |
| BUG-044 | context domain leak | 🟡 | 📋 |
| BUG-058 | Manager `line_text_encrypted` | 🟡 | 📋 |
| BACKLOG-028 | GitHub | 🔴 | 📋 46 |
| BACKLOG-043 | Прогресс сканера в WebUI | 🟡 | 🔄 |
| BACKLOG-044 | `/metrics` защита | 🟡 | 📋 |

---

## 📋 v3.1.0 — RUST + DLP (📋 ПЛАНИРУЕТСЯ)

**См. предыдущую версию.** Добавлено:

- **Auth Hardening** (из Блока 2): `jti` + `iat` + Redis blacklist (BUG-041 + TEST-NOTE-2.6a)
- **Presidio** производительность (BACKLOG-063)
- **Bug-048/049** автоматизация chaos (BACKLOG-049)

---

## 📊 Статистика

| Версия | Задач | Выполнено | Прогресс |
|--------|-------|-----------|----------|
| v1.0.0-v2.1.0 | 27 | 27 | 100% ✅ |
| v3.0.0 | 35 + 20 (баги Блока 2) | 22 | 40% 🔄 |
| v3.1.0 | 12 | 0 | 0% 📋 |
| v4.0.0 | 9 | 0 | 0% 📋 |
| **ИТОГО** | **103** | **49** | **48%** |

---

## 📝 Шаблон новой задачи
| BACKLOG-XXX / BUG-XXX | Название | 🔴/🟡/🟢 | 📋/🔄/✅/❌ |

text

**Приоритеты:** 🔴 критично / 🟡 важно / 🟢 nice-to-have
**Статусы:** 📋 запланировано / 🔄 в работе / ✅ выполнено / ❌ отменено