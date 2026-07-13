import csv
import json
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

EVENTS_FILE = Path("events/phasmida_events.csv")
REPORTS_DIR = Path("reports")


def severity_score(severity):
    return {
        "LOW": 1,
        "MEDIUM": 2,
        "HIGH": 3,
        "CRITICAL": 4
    }.get(severity, 0)


def load_events():
    if not EVENTS_FILE.exists():
        return []

    with EVENTS_FILE.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_report_data(events):
    critical = sum(1 for e in events if e["severity"] == "CRITICAL")
    high = sum(1 for e in events if e["severity"] == "HIGH")
    medium = sum(1 for e in events if e["severity"] == "MEDIUM")

    events_sorted = sorted(
        events,
        key=lambda e: severity_score(e.get("severity", "")),
        reverse=True
    )

    return {
        "report_type": "PHASMIDA Incident Report",
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "total_events": len(events),
        "severity_summary": {
            "CRITICAL": critical,
            "HIGH": high,
            "MEDIUM": medium
        },
        "most_critical_event": events_sorted[0] if events_sorted else None,
        "events": events,
        "recommendations": [
            "Verificar el origen del tráfico no autorizado.",
            "Mantener el filtrado IPTables activo.",
            "Revisar la clave compartida HMAC-SHA256.",
            "Analizar las tramas NMEA asociadas al incidente.",
            "Conservar este informe como evidencia del experimento."
        ]
    }


def save_json(report_data, path):
    path.write_text(
        json.dumps(report_data, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )


def save_txt(report_data, path):
    lines = []
    lines.append("=" * 70)
    lines.append("PHASMIDA INCIDENT REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Fecha de generación: {report_data['generated_at_utc']}")
    lines.append(f"Número total de eventos: {report_data['total_events']}")
    lines.append("")
    lines.append("RESUMEN DE SEVERIDAD")
    for sev, count in report_data["severity_summary"].items():
        lines.append(f"  {sev}: {count}")

    top = report_data["most_critical_event"]
    if top:
        lines.append("")
        lines.append("EVENTO MÁS CRÍTICO")
        lines.append("-" * 70)
        lines.append(f"Timestamp: {top['timestamp']}")
        lines.append(f"Tipo:      {top['alert_type']}")
        lines.append(f"Severidad: {top['severity']}")
        lines.append(f"Origen:    {top['source_ip']}")
        lines.append(f"Mensaje:   {top['message']}")
        lines.append(f"Trama:     {top['raw_sentence']}")

    lines.append("")
    lines.append("CRONOLOGÍA DE EVENTOS")
    lines.append("-" * 70)

    for e in report_data["events"]:
        lines.append(
            f"[{e['timestamp']}] {e['severity']} | "
            f"{e['alert_type']} | {e['source_ip']} | {e['message']}"
        )

    lines.append("")
    lines.append("RECOMENDACIONES")
    lines.append("-" * 70)
    for rec in report_data["recommendations"]:
        lines.append(f"- {rec}")

    path.write_text("\n".join(lines), encoding="utf-8")


def save_pdf(report_data, path):
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    y = height - 50

    def write_line(text, size=10, bold=False):
        nonlocal y

        if y < 60:
            c.showPage()
            y = height - 50

        font = "Helvetica-Bold" if bold else "Helvetica"
        c.setFont(font, size)
        c.drawString(50, y, text[:115])
        y -= 16

    write_line("PHASMIDA INCIDENT REPORT", 16, True)
    write_line("=" * 90)
    write_line(f"Fecha de generación: {report_data['generated_at_utc']}")
    write_line(f"Número total de eventos: {report_data['total_events']}")
    write_line("")

    write_line("RESUMEN DE SEVERIDAD", 12, True)
    for sev, count in report_data["severity_summary"].items():
        write_line(f"{sev}: {count}")

    top = report_data["most_critical_event"]
    if top:
        write_line("")
        write_line("EVENTO MÁS CRÍTICO", 12, True)
        write_line(f"Timestamp: {top['timestamp']}")
        write_line(f"Tipo: {top['alert_type']}")
        write_line(f"Severidad: {top['severity']}")
        write_line(f"Origen: {top['source_ip']}")
        write_line(f"Mensaje: {top['message']}")
        write_line(f"Trama: {top['raw_sentence']}")

    write_line("")
    write_line("CRONOLOGÍA DE EVENTOS", 12, True)

    for e in report_data["events"]:
        write_line(
            f"[{e['timestamp']}] {e['severity']} | "
            f"{e['alert_type']} | {e['source_ip']}"
        )
        write_line(f"  {e['message']}")

    write_line("")
    write_line("RECOMENDACIONES", 12, True)

    for rec in report_data["recommendations"]:
        write_line(f"- {rec}")

    c.save()


def generate_report():
    REPORTS_DIR.mkdir(exist_ok=True)

    events = load_events()
    report_data = build_report_data(events)

    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    txt_path = REPORTS_DIR / f"incident_report_{now}.txt"
    json_path = REPORTS_DIR / f"incident_report_{now}.json"
    pdf_path = REPORTS_DIR / f"incident_report_{now}.pdf"

    save_txt(report_data, txt_path)
    save_json(report_data, json_path)
    save_pdf(report_data, pdf_path)

    print(f"TXT generado:  {txt_path}")
    print(f"JSON generado: {json_path}")
    print(f"PDF generado:  {pdf_path}")


if __name__ == "__main__":
    generate_report()
