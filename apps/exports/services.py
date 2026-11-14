"""X01 exports (§6.8). Reads the values stored when the evaluation was finalized; computes nothing."""
import csv
import io
import re

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.evaluations import workflow
from apps.evaluations.services import ESCALA, TEXTOS_RECOMENDACION, formatear_pm

CSV_HEADER = [
    "evaluación", "software", "factor", "alcance", "ID", "IS", "IR",
    "relevante", "PM", "FODA", "subfactor", "calificación",
]
PDF_SECTIONS = {"recomendacion", "foda", "detalle", "respuestas"}
DEFAULT_PDF_SECTIONS = {"recomendacion", "foda", "detalle"}
FODA_ORDER = ["Fortaleza", "Debilidad", "Oportunidad", "Amenaza"]
BRAND = colors.HexColor("#fb7a35")


def _pm(value):
    return formatear_pm(value) if value is not None else ""


def _local_date(value, fmt):
    return timezone.localtime(value).strftime(fmt) if value else ""


def export_filename(evaluation, extension):
    """GUIOS_<software>_<fecha>.<ext>, safe for every operating system."""
    software = re.sub(r"[^\w.-]+", "_", str(evaluation.software)).strip("_")
    return f"GUIOS_{software}_{_local_date(evaluation.finished_at, '%Y-%m-%d')}.{extension}"


def _factors(evaluation):
    return list(
        evaluation.factors.select_related("factor")
        .prefetch_related("answers", "factor__subfactors")
        .order_by("factor__order")
    )


def build_csv(evaluation):
    """One row per subfactor (61). Semicolon-separated because PM uses a decimal comma;
    UTF-8 with BOM so Excel shows accents correctly."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(CSV_HEADER)
    for ev_factor in _factors(evaluation):
        answers = {answer.subfactor_id: answer.value for answer in ev_factor.answers.all()}
        for subfactor in ev_factor.factor.subfactors.all():
            value = answers.get(subfactor.pk) if ev_factor.is_relevant else None
            writer.writerow([
                evaluation.pk,
                str(evaluation.software),
                ev_factor.factor.name,
                ev_factor.scope.capitalize(),
                ev_factor.decision_importance or "",
                ev_factor.suggested_importance,
                ev_factor.relative_importance or "",
                "Sí" if ev_factor.is_relevant else "No",
                _pm(ev_factor.pm),
                ev_factor.foda,
                subfactor.name,
                value or "",
            ])
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def report_data(evaluation):
    """Everything the PDF prints, in plain values (also what H02 shows)."""
    factors = _factors(evaluation)
    result = workflow.results(evaluation)
    return {
        "header": {
            "Organización": evaluation.organization.name,
            "Software": str(evaluation.software),
            "Evaluador": evaluation.author.get_full_name() or evaluation.author.email,
            "Fecha": _local_date(evaluation.finished_at, "%d/%m/%Y"),
            "Versión de catálogo": f"v{evaluation.catalog_version.number}",
        },
        "factors": [
            {
                "name": f.factor.name,
                "scope": f.scope.capitalize(),
                "id": f.decision_importance,
                "is": f.suggested_importance,
                "ir": ESCALA.get(f.relative_importance, ""),
                "pm": _pm(f.pm) if f.is_relevant else "",
                "foda": f.foda if f.is_relevant else "No evaluado",
                "answers": [
                    (s.name, {a.subfactor_id: a.value for a in f.answers.all()}.get(s.pk))
                    for s in f.factor.subfactors.all()
                ] if f.is_relevant else [],
            }
            for f in factors
        ],
        "recommendation": evaluation.recommendation,
        "recommendation_text": TEXTOS_RECOMENDACION.get(evaluation.recommendation, ""),
        "supporting": [f"{row.factor.name} · PM {_pm(row.pm)} · {row.foda}" for row in result["supporting"]],
        "foda": {key: [f.factor.name for f in factors if f.foda == key] for key in FODA_ORDER},
    }


def _table(rows, widths, header=True):
    table = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e4e4e7")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f4f4f5")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    table.setStyle(TableStyle(style))
    return table


def build_pdf(evaluation, sections=None):
    sections = (set(sections) & PDF_SECTIONS) or DEFAULT_PDF_SECTIONS
    data = report_data(evaluation)
    styles = getSampleStyleSheet()
    title = styles["Title"].clone("GuiosTitle", alignment=0, fontSize=18, textColor=colors.HexColor("#18181b"))
    heading = styles["Heading3"].clone("GuiosHeading", textColor=colors.HexColor("#18181b"), spaceBefore=12)
    body = styles["BodyText"].clone("GuiosBody", fontSize=9, leading=12)
    cell = body.clone("GuiosCell", fontSize=8, leading=10)

    story = [
        Paragraph(f"GUIOS PRO · {data['header']['Software']}", title),
        _table([[key, value] for key, value in data["header"].items()], [4 * cm, 13 * cm], header=False),
    ]
    if "recomendacion" in sections:
        letter = Paragraph(f"<font color='#fb7a35'><b>Recomendación {data['recommendation']}</b></font>", heading)
        story += [letter, Paragraph(data["recommendation_text"], body), Spacer(1, 6),
                  Paragraph("<b>Factores que la sustentan</b>", body)]
        story += [Paragraph(f"• {item}", body) for item in data["supporting"]] or [Paragraph("—", body)]
    if "foda" in sections:
        story.append(Paragraph("Matriz FODA", heading))
        rows = [["Fortalezas", "Debilidades"], [", ".join(data["foda"]["Fortaleza"]) or "—", ", ".join(data["foda"]["Debilidad"]) or "—"],
                ["Oportunidades", "Amenazas"], [", ".join(data["foda"]["Oportunidad"]) or "—", ", ".join(data["foda"]["Amenaza"]) or "—"]]
        rows = [[Paragraph(text, cell) for text in row] for row in rows]
        story.append(_table(rows, [8.5 * cm, 8.5 * cm], header=False))
    if "detalle" in sections:
        story.append(Paragraph("Detalle por factor", heading))
        rows = [["Factor", "Alcance", "ID", "IS", "IR", "PM", "FODA"]]
        rows += [[Paragraph(f["name"], cell), f["scope"], f["id"] or "", f["is"], f["ir"], f["pm"], f["foda"]] for f in data["factors"]]
        story.append(_table(rows, [5.5 * cm, 1.8 * cm, 1 * cm, 1 * cm, 2.4 * cm, 1.3 * cm, 2.6 * cm]))
    if "respuestas" in sections:
        story.append(Paragraph("Respuestas de los subfactores", heading))
        for factor in (f for f in data["factors"] if f["answers"]):
            story.append(Paragraph(f"<b>{factor['name']}</b>", body))
            rows = [["Subfactor", "Calificación"]] + [[Paragraph(name, cell), value or ""] for name, value in factor["answers"]]
            story.append(_table(rows, [14.5 * cm, 2.5 * cm]))

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                                 title=export_filename(evaluation, "pdf"), author="GUIOS PRO")
    document.build(story)
    return buffer.getvalue()
