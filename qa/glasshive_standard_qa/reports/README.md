# GlassHive Standard QA Reports

Private local live-run evidence is ignored from this folder. Public reports committed here must use
synthetic project names, sanitized paths, and the standard QA evidence template.

## 2026-06-24 Shared Upload Materialization And Verifier QA

Public-safe summary for `GH-STD-002`: shared-upload deployments must prove that GlassHive receives
the original uploaded bytes under `uploads/`, not only filename metadata or extracted text. The live
issue fixed on 2026-06-24 had two generic causes: upload storage was not visible to the worker, and
the evidence verifier treated input/source PDF wording as a required PDF output artifact even when
the requested deliverable was HTML.

Regression coverage now includes:

- bounded/logged legacy upload compatibility fallback,
- request-file metadata preferred over fallback,
- MIME and source-byte phrases such as `application/pdf`, `%PDF`, and `PDF bytes` ignored as output
  format requirements,
- requested output formats such as `HTML summary`, `xlsx workbook`, and `save as report.html`
  preserved,
- live browser upload/download/workspace-render QA on a private enterprise deployment, with raw
  tenant/resource/run evidence kept in the private deployment evidence repo.
