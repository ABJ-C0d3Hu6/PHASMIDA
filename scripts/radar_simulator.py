import json
import math
import os
import random
import time
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

STATE_FILE = os.getenv(
    "PHASMIDA_STATE_FILE",
    "events/nmea_state.json"
)

MAX_RANGE_NM = 12.0
NUM_TARGETS = 8
REFRESH_SECONDS = 1.0
STALE_AFTER_SECONDS = 10

RADAR_GREEN = "#39FF14"
RADAR_LIGHT_GREEN = "#BFFF00"
RADAR_DARK_GREEN = "#006400"

DEFAULT_NAVIGATION = {
    "latitude": 38.335,
    "longitude": -0.430,
    "heading_deg": 75.0,
    "course_deg": 75.0,
    "speed_knots": 10.5,
    "updated_at": None,
    "sentence_type": None,
    "source_ip": None
}


# ==========================================================
# CONFIGURACIÓN DE STREAMLIT
# ==========================================================

st.set_page_config(
    page_title="RADAR simulado",
    layout="wide"
)


# ==========================================================
# ESTILO VISUAL
# ==========================================================

st.markdown(
    """
    <style>
    .stApp {
        background-color: #000000;
        color: #39FF14;
    }

    h1, h2, h3, h4, p, span, div {
        color: #39FF14 !important;
    }

    [data-testid="stMetric"] {
        background-color: #050805;
        border: 1px solid #1f7a1f;
        padding: 15px;
        border-radius: 8px;
    }

    [data-testid="stMetricLabel"] {
        color: #7CFC00 !important;
    }

    [data-testid="stMetricValue"] {
        color: #39FF14 !important;
    }

    [data-testid="stAlert"] {
        background-color: #071007;
        border: 1px solid #1f7a1f;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ==========================================================
# LECTURA DEL ESTADO PHASMIDA CORE
# ==========================================================

def load_nmea_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        return state if isinstance(state, dict) else {}

    except (OSError, json.JSONDecodeError):
        return {}


def build_navigation_state(state: dict) -> dict:
    position = state.get("position", {})
    navigation = state.get("navigation", {})

    heading = navigation.get("heading_deg")
    course = navigation.get("course_deg")

    resolved_heading = (
        float(heading)
        if heading is not None
        else float(course)
        if course is not None
        else DEFAULT_NAVIGATION["heading_deg"]
    )

    resolved_course = (
        float(course)
        if course is not None
        else resolved_heading
    )

    latitude = position.get("latitude")
    longitude = position.get("longitude")
    speed = navigation.get("speed_knots")

    return {
        "latitude": (
            float(latitude)
            if latitude is not None
            else DEFAULT_NAVIGATION["latitude"]
        ),
        "longitude": (
            float(longitude)
            if longitude is not None
            else DEFAULT_NAVIGATION["longitude"]
        ),
        "heading_deg": resolved_heading % 360.0,
        "course_deg": resolved_course % 360.0,
        "speed_knots": (
            float(speed)
            if speed is not None
            else DEFAULT_NAVIGATION["speed_knots"]
        ),
        "updated_at": state.get("updated_at"),
        "sentence_type": state.get("last_sentence_type"),
        "source_ip": state.get("source_ip"),
        "security": state.get("security", {})
    }


def get_state_age(updated_at: str | None) -> float | None:
    if not updated_at:
        return None

    try:
        state_time = datetime.fromisoformat(updated_at)
        now = datetime.now(timezone.utc)

        return abs((now - state_time).total_seconds())

    except (TypeError, ValueError):
        return None


# ==========================================================
# GENERACIÓN Y MOVIMIENTO DE BLANCOS
# ==========================================================

def generate_targets() -> list[dict]:
    targets = []

    for index in range(NUM_TARGETS):
        targets.append({
            "id": f"T{index + 1:02d}",
            "bearing": random.uniform(0.0, 360.0),
            "range_nm": random.uniform(0.8, MAX_RANGE_NM - 0.5),
            "speed_knots": random.uniform(2.0, 22.0),
            "course": random.uniform(0.0, 360.0),
            "status": random.choice([
                "normal",
                "normal",
                "normal",
                "suspicious"
            ])
        })

    return targets


def update_targets(
    targets: list[dict],
    interval_seconds: float
) -> list[dict]:
    """
    Actualiza suavemente los blancos radar para evitar que
    cambien de posición de manera aleatoria en cada refresco.
    """

    for target in targets:
        target_speed = float(target["speed_knots"])
        target_course = math.radians(float(target["course"]))
        target_bearing = math.radians(float(target["bearing"]))
        target_range = float(target["range_nm"])

        distance_nm = (
            target_speed
            * interval_seconds
            / 3600.0
        )

        x = target_range * math.sin(target_bearing)
        y = target_range * math.cos(target_bearing)

        x += distance_nm * math.sin(target_course)
        y += distance_nm * math.cos(target_course)

        new_range = math.sqrt(x ** 2 + y ** 2)
        new_bearing = (
            math.degrees(math.atan2(x, y))
            % 360.0
        )

        if new_range > MAX_RANGE_NM:
            new_range = random.uniform(
                1.0,
                MAX_RANGE_NM * 0.7
            )
            new_bearing = random.uniform(0.0, 360.0)

        target["range_nm"] = new_range
        target["bearing"] = new_bearing

        target["course"] = (
            float(target["course"])
            + random.uniform(-0.4, 0.4)
        ) % 360.0

    return targets


def build_targets_dataframe(
    targets: list[dict],
    own_heading: float
) -> pd.DataFrame:
    rows = []

    for target in targets:
        absolute_bearing = float(target["bearing"])

        # Presentación Head-Up:
        # la proa del buque se mantiene en 0º.
        relative_bearing = (
            absolute_bearing - own_heading
        ) % 360.0

        rows.append({
            "id": target["id"],
            "bearing": round(relative_bearing, 1),
            "absolute_bearing": round(absolute_bearing, 1),
            "range_nm": round(float(target["range_nm"]), 2),
            "speed_knots": round(
                float(target["speed_knots"]),
                1
            ),
            "course": round(float(target["course"]), 1),
            "status": target["status"]
        })

    return pd.DataFrame(rows)


# ==========================================================
# ESTADO DE SESIÓN
# ==========================================================

if "radar_targets" not in st.session_state:
    st.session_state.radar_targets = generate_targets()

st.session_state.radar_targets = update_targets(
    st.session_state.radar_targets,
    REFRESH_SECONDS
)


# ==========================================================
# DATOS DEL CORE
# ==========================================================

state = load_nmea_state()
navigation = build_navigation_state(state)
state_age = get_state_age(navigation["updated_at"])

df = build_targets_dataframe(
    st.session_state.radar_targets,
    navigation["heading_deg"]
)


# ==========================================================
# CABECERA
# ==========================================================

st.title("RADAR simulado")

st.caption(
    "Presentación polar PPI en modo Head-Up integrada "
    "con PHASMIDA Core"
)

if not state:
    st.warning(
        "No se ha encontrado el estado de PHASMIDA Core. "
        "Se muestran valores de respaldo."
    )

elif state_age is None or state_age > STALE_AFTER_SECONDS:
    st.warning(
        "El estado NMEA no se ha actualizado recientemente."
    )

else:
    st.success(
        "Radar conectado correctamente a PHASMIDA Core."
    )


# ==========================================================
# MÉTRICAS
# ==========================================================

suspicious_count = len(
    df[df["status"] == "suspicious"]
)

col1, col2, col3, col4, col5, col6 = st.columns(6)

col1.metric(
    "Blancos detectados",
    len(df)
)

col2.metric(
    "Alcance",
    f"{MAX_RANGE_NM:.0f} NM"
)

col3.metric(
    "Sospechosos",
    suspicious_count
)

col4.metric(
    "Rumbo propio",
    f"{navigation['heading_deg']:.1f}º"
)

col5.metric(
    "Velocidad propia",
    f"{navigation['speed_knots']:.1f} kn"
)

col6.metric(
    "Hora UTC",
    datetime.now(timezone.utc).strftime("%H:%M:%S")
)


# ==========================================================
# GRÁFICO RADAR
# ==========================================================

fig = go.Figure()


# Blancos normales
normal_df = df[df["status"] == "normal"]

if not normal_df.empty:
    fig.add_trace(
        go.Scatterpolar(
            r=normal_df["range_nm"],
            theta=normal_df["bearing"],
            mode="markers+text",
            text=normal_df["id"],
            textposition="top center",
            marker=dict(
                size=13,
                color=RADAR_GREEN,
                symbol="circle",
                line=dict(
                    color=RADAR_LIGHT_GREEN,
                    width=1.5
                )
            ),
            textfont=dict(
                color=RADAR_GREEN,
                size=13,
                family="Courier New"
            ),
            customdata=normal_df[
                [
                    "speed_knots",
                    "course",
                    "status",
                    "absolute_bearing"
                ]
            ],
            hovertemplate=(
                "Blanco: %{text}<br>"
                "Distancia: %{r:.2f} NM<br>"
                "Demora relativa: %{theta:.1f}º<br>"
                "Demora verdadera: %{customdata[3]:.1f}º<br>"
                "Velocidad: %{customdata[0]:.1f} kn<br>"
                "Curso: %{customdata[1]:.1f}º<br>"
                "Estado: %{customdata[2]}"
                "<extra></extra>"
            )
        )
    )


# Blancos sospechosos
suspicious_df = df[df["status"] == "suspicious"]

if not suspicious_df.empty:
    fig.add_trace(
        go.Scatterpolar(
            r=suspicious_df["range_nm"],
            theta=suspicious_df["bearing"],
            mode="markers+text",
            text=suspicious_df["id"],
            textposition="top center",
            marker=dict(
                size=15,
                color="#ff3b30",
                symbol="diamond",
                line=dict(
                    color="#ffcc00",
                    width=2
                )
            ),
            textfont=dict(
                color="#ffcc00",
                size=13,
                family="Courier New"
            ),
            customdata=suspicious_df[
                [
                    "speed_knots",
                    "course",
                    "status",
                    "absolute_bearing"
                ]
            ],
            hovertemplate=(
                "Blanco: %{text}<br>"
                "Distancia: %{r:.2f} NM<br>"
                "Demora relativa: %{theta:.1f}º<br>"
                "Demora verdadera: %{customdata[3]:.1f}º<br>"
                "Velocidad: %{customdata[0]:.1f} kn<br>"
                "Curso: %{customdata[1]:.1f}º<br>"
                "Estado: %{customdata[2]}"
                "<extra></extra>"
            )
        )
    )


# Buque propio
fig.add_trace(
    go.Scatterpolar(
        r=[0],
        theta=[0],
        mode="markers",
        marker=dict(
            size=12,
            color=RADAR_GREEN,
            symbol="triangle-up"
        ),
        hovertemplate=(
            "Buque propio<br>"
            f"Rumbo: {navigation['heading_deg']:.1f}º<br>"
            f"Velocidad: {navigation['speed_knots']:.1f} kn"
            "<extra></extra>"
        )
    )
)


# Línea de proa
fig.add_trace(
    go.Scatterpolar(
        r=[0, MAX_RANGE_NM],
        theta=[0, 0],
        mode="lines",
        line=dict(
            color=RADAR_LIGHT_GREEN,
            width=1,
            dash="dot"
        ),
        hoverinfo="skip"
    )
)


# Barrido radar
sweep_angle = (
    time.time() * 35.0
) % 360.0

for alpha, offset, width in [
    (0.08, 18, 10),
    (0.15, 12, 8),
    (0.25, 6, 5)
]:
    fig.add_trace(
        go.Scatterpolar(
            r=[0, MAX_RANGE_NM],
            theta=[
                sweep_angle - offset,
                sweep_angle - offset
            ],
            mode="lines",
            line=dict(
                color=f"rgba(57,255,20,{alpha})",
                width=width
            ),
            hoverinfo="skip"
        )
    )

fig.add_trace(
    go.Scatterpolar(
        r=[0, MAX_RANGE_NM],
        theta=[sweep_angle, sweep_angle],
        mode="lines",
        line=dict(
            color=RADAR_GREEN,
            width=3
        ),
        hoverinfo="skip"
    )
)


# ==========================================================
# ESTILO DEL GRÁFICO
# ==========================================================

fig.update_layout(
    template=None,
    paper_bgcolor="black",
    plot_bgcolor="black",
    font=dict(
        color=RADAR_GREEN,
        family="Courier New"
    ),
    polar=dict(
        bgcolor="black",
        radialaxis=dict(
            visible=True,
            range=[0, MAX_RANGE_NM],
            color=RADAR_GREEN,
            tickfont=dict(
                color=RADAR_GREEN,
                size=12
            ),
            gridcolor=RADAR_DARK_GREEN,
            linecolor=RADAR_GREEN,
            showline=True,
            ticksuffix=" NM"
        ),
        angularaxis=dict(
            color=RADAR_GREEN,
            tickfont=dict(
                color=RADAR_GREEN,
                size=12
            ),
            gridcolor=RADAR_DARK_GREEN,
            linecolor=RADAR_GREEN,
            rotation=90,
            direction="clockwise",
            tickmode="array",
            tickvals=[
                0, 45, 90, 135,
                180, 225, 270, 315
            ],
            ticktext=[
                "PROA",
                "045",
                "090",
                "135",
                "POPA",
                "225",
                "270",
                "315"
            ]
        )
    ),
    showlegend=False,
    height=700,
    margin=dict(
        l=20,
        r=20,
        t=20,
        b=20
    )
)

st.plotly_chart(
    fig,
    use_container_width=True,
    theme=None,
    key="phasmida_radar"
)


# ==========================================================
# ESTADO NMEA
# ==========================================================

st.subheader("Estado de navegación recibido")

status_col1, status_col2, status_col3, status_col4 = st.columns(4)

status_col1.metric(
    "Latitud",
    f"{navigation['latitude']:.6f}"
)

status_col2.metric(
    "Longitud",
    f"{navigation['longitude']:.6f}"
)

status_col3.metric(
    "Última sentencia",
    navigation["sentence_type"] or "N/D"
)

status_col4.metric(
    "Edad del estado",
    (
        f"{state_age:.1f} s"
        if state_age is not None
        else "N/D"
    )
)


# ==========================================================
# TABLA DE BLANCOS
# ==========================================================

st.subheader("Tabla de blancos radar")

table_df = df.rename(
    columns={
        "id": "ID",
        "bearing": "Demora relativa (º)",
        "absolute_bearing": "Demora verdadera (º)",
        "range_nm": "Distancia (NM)",
        "speed_knots": "Velocidad (kn)",
        "course": "Curso (º)",
        "status": "Estado"
    }
)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# ==========================================================
# REFRESCO
# ==========================================================

time.sleep(REFRESH_SECONDS)
st.rerun()
