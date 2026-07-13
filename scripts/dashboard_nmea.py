import subprocess
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

EVENTS_FILE = Path("events/phasmida_events.csv")
REPORTS_DIR = Path("reports")


st.set_page_config(
    page_title="PHASMIDA SIEM",
    layout="wide"
)

st.title("PHASMIDA SIEM")
st.caption("Monitorización de eventos NMEA, alertas IDS e informes de incidentes")


@st.cache_data(ttl=2)
def load_events():
    if not EVENTS_FILE.exists():
        return pd.DataFrame(
            columns=[
                "timestamp",
                "alert_type",
                "severity",
                "source_ip",
                "message",
                "raw_sentence"
            ]
        )

    df = pd.read_csv(EVENTS_FILE)

    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.sort_values("timestamp", ascending=False)

    return df


def severity_rank(severity):
    ranks = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
        "INFO": 0
    }
    return ranks.get(str(severity).upper(), 0)


def get_system_status(df):
    if df.empty:
        return "NORMAL", "No hay incidentes registrados"

    max_rank = df["severity"].apply(severity_rank).max()

    if max_rank >= 4:
        return "CRITICAL", "Incidente crítico detectado"
    if max_rank == 3:
        return "WARNING", "Alertas de severidad alta"
    if max_rank == 2:
        return "WARNING", "Alertas de severidad media"

    return "NORMAL", "Sistema sin alertas relevantes"


def generate_report():
    result = subprocess.run(
        ["python3", "ids/report_generator.py"],
        capture_output=True,
        text=True
    )

    return result.stdout, result.stderr


df = load_events()
status, status_msg = get_system_status(df)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Estado del sistema", status)
col2.metric("Eventos registrados", len(df))
col3.metric(
    "Alertas críticas",
    int((df["severity"] == "CRITICAL").sum()) if not df.empty else 0
)
col4.metric(
    "Fuentes detectadas",
    df["source_ip"].nunique() if not df.empty else 0
)

st.info(status_msg)

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("Eventos registrados")

    if df.empty:
        st.warning("Todavía no hay eventos registrados.")
    else:
        st.dataframe(
            df[
                [
                    "timestamp",
                    "severity",
                    "alert_type",
                    "source_ip",
                    "message",
                    "raw_sentence"
                ]
            ],
            use_container_width=True,
            height=360
        )

with right:
    st.subheader("Último evento")

    if df.empty:
        st.write("Sin eventos.")
    else:
        last = df.iloc[0]

        st.write(f"**Severidad:** {last['severity']}")
        st.write(f"**Tipo:** {last['alert_type']}")
        st.write(f"**Origen:** `{last['source_ip']}`")
        st.write(f"**Mensaje:** {last['message']}")
        st.code(last["raw_sentence"], language="text")

st.divider()

if not df.empty:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Eventos por severidad")

        severity_chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("severity:N", title="Severidad"),
                y=alt.Y("count():Q", title="Número de eventos"),
                tooltip=["severity:N", "count():Q"]
            )
            .properties(height=300)
        )

        st.altair_chart(severity_chart, use_container_width=True)

    with col_b:
        st.subheader("Eventos por tipo")

        type_chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X("count():Q", title="Número de eventos"),
                y=alt.Y("alert_type:N", title="Tipo de alerta", sort="-x"),
                tooltip=["alert_type:N", "count():Q"]
            )
            .properties(height=300)
        )

        st.altair_chart(type_chart, use_container_width=True)

st.divider()

st.subheader("Generación de informes")

if st.button("Generar informe de incidente"):
    stdout, stderr = generate_report()

    if stderr:
        st.error(stderr)
    else:
        st.success("Informe generado correctamente.")
        st.code(stdout, language="text")

reports = sorted(REPORTS_DIR.glob("incident_report_*"), reverse=True)

if reports:
    st.write("Últimos informes generados:")

    for report in reports[:6]:
        st.write(f"- `{report}`")
