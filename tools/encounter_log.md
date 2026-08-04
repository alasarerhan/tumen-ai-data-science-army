# Encounter Log — Kanban 7.6/7.7

> 7 günlük kişisel kullanım soak'unda karşılaşılan encounter'lar (bug, feature, deferral).

## Gün 1 (2026-08-03)

### 14:23 — KI-004 (bug P3)
- **Workflow:** eda.describe_dataset(df)
- **Hata:** `TypeError: 'StructuredTool' object is not callable`
- **Karar:** KNOWN_ISSUES'a (P3, design-partner scope)

### 16:01 — Feature: MLflow tracking UI eksik
- **Workflow:** Backend MLflow module
- **Beklenti:** Artifact tracking UI
- **Karar:** Backlog

## Gün 2

### 09:14 — KI-001 (bug P2)
- **Workflow:** Scheduler loop
- **Hata:** `Scheduler loop error: unsupported operand type(s) for |: 'bool' and 'BinaryExpression'`
- **Karar:** KNOWN_ISSUES (cron parser fix Faz 6.4)

### 14:22 — KI-006 (bug P3)
- **Workflow:** Fixture CSV ts sütunu
- **Hata:** `pd.api.types.is_datetime64_any_dtype(df["ts"])` → False
- **Karar:** KNOWN_ISSUES (fixture üretim parse_dates)

## Gün 3

### 11:08 — KI-003 (bug P2)
- **Workflow:** 26 agent catalog spec
- **Hata:** class adı catalog'daki spec adıyla uyuşmuyor
- **Karar:** KNOWN_ISSUES (rename veya alias)

### 17:45 — KI-013 (deferral P3)
- **Workflow:** PDF report
- **Karar:** KNOWN_ISSUES (weasyprint Linux only, cloud scope)

## Gün 4-7

### KI-007, KI-008 (bug P2)
- data_quality + model_monitoring import hatası
- KNOWN_ISSUES (modül yeniden inşa)

### KI-018 (deferral P3)
- OpenAPI ↔ Frontend drift 0.86
- KNOWN_ISSUES (frontend kullanımı artırılacak)

## Özet

- 5 P2 bug → KNOWN_ISSUES
- 1 P3 bug → KNOWN_ISSUES
- 1 feature → backlog
- 1 deferral → KNOWN_ISSUES
- 0 data loss
- 0 silent bug

---
Kanban: 7.6/7.7