import json
import os
import time
from datetime import datetime, timezone

import numpy as np
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

REFRESH_SECONDS = 1.0
WINDOW_SIZE = 120

MAX_DEPTH = 100.0
BASE_DEPTH = 45.0

ALERT_DEPTH = 12.0
CRITICAL_DEPTH = 6.0

STALE_AFTER_SECONDS = 10.0


# ==========================================================
# PALETA VISUAL
# ==========================================================

BACKGROUND_BLUE = "#020817"
PANEL_BLUE = "#071426"

PRIMARY_BLUE = "#2196F3"
LIGHT_BLUE = "#64B5F6"
PALE_BLUE = "#90CAF9"
DARK_BLUE = "#0D47A1"
GRID_BLUE = "#12355B"
DEEP_BLUE = "#001F3F"

ALERT_YELLOW = "#FFD600"
CRITICAL_RED = "#FF1744"
WHITE_BLUE = "#E3F2FD"


# ==========================================================
# CONFIGURACIÓN DE STREAMLIT
# ==========================================================

st.set_page_config(
    page_title="Sonda PHASMIDA",
    layout="wide"
)


# ==========================================================
# ESTILO VISUAL
# ==========================================================

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {BACKGROUND_BLUE};
        color: {PALE_BLUE};
    }}

    h1, h2, h3, h4 {{
        color: {LIGHT_BLUE} !important;
    }}

    p, span, div {{
        color: {PALE_BLUE};
    }}

    [data-testid="stMetric"] {{
        background-color: {PANEL_BLUE};
        border: 1px solid {DARK_BLUE};
        padding: 14px;
        border-radius: 8px;
    }}

    [data-testid="stMetricLabel"] {{
        color: {LIGHT_BLUE} !important;
    }}

    [data-testid="stMetricValue"] {{
        color: {WHITE_BLUE} !important;
    }}

    [data-testid="stAlert"] {{
        background-color: {PANEL_BLUE};
    }}
    </style>
    """,
    unsafe_allow_html=True
)


# ==========================================================
# LECTURA DEL ESTADO PHASMIDA CORE
# ==========================================================

def load_nmea_state() -> dict:
    """
    Lee el estado compartido generado por PHASMIDA Core.
    """

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        return state if isinstance(state, dict) else {}

    except (OSError, json.JSONDecodeError):
        return {}


def get_state_age(updated_at: str | None) -> float | None:
    """
    Devuelve la antigüedad del estado en segundos.
    """

    if not updated_at:
        return None

    try:
        state_time = datetime.fromisoformat(updated_at)
        now = datetime.now(timezone.utc)

        return abs(
            (now - state_time).total_seconds()
        )

    except (TypeError, ValueError):
        return None


def get_core_depth(state: dict) -> float | None:
    """
    Obtiene la profundidad publicada por PHASMIDA Core.
    """

    depth_section = state.get("depth", {})

    if not isinstance(depth_section, dict):
        return None

    depth = depth_section.get("meters")

    if depth is None:
        return None

    try:
        return float(depth)

    except (TypeError, ValueError):
        return None


# ==========================================================
# SIMULACIÓN DE RESPALDO
# ==========================================================

def generate_fallback_depth(sample_index: int) -> float:
    """
    Genera un perfil de profundidad suave cuando todavía
    no existen tramas DBT o DPT en el bus NMEA.
    """

    seabed = (
        BASE_DEPTH
        + 8.0 * np.sin(sample_index / 22.0)
        + 4.0 * np.sin(sample_index / 8.0)
        + np.random.normal(0.0, 0.35)
    )

    return float(
        np.clip(
            seabed,
            3.0,
            MAX_DEPTH - 5.0
        )
    )


# ==========================================================
# CLASIFICACIÓN DEL RIESGO
# ==========================================================

def get_risk_level(depth: float) -> tuple[str, str]:
    if depth <= CRITICAL_DEPTH:
        return (
            "CRÍTICO",
            "Riesgo elevado de encallamiento"
        )

    if depth <= ALERT_DEPTH:
        return (
            "ALERTA",
            "Bajo fondo detectado"
        )

    return (
        "NORMAL",
        "Profundidad dentro del margen seguro"
    )


# ==========================================================
# ESTADO DE SESIÓN
# ==========================================================

if "echo_sample_index" not in st.session_state:
    st.session_state.echo_sample_index = 0

if "depth_history" not in st.session_state:
    st.session_state.depth_history = []

if "depth_source_history" not in st.session_state:
    st.session_state.depth_source_history = []


# ==========================================================
# OBTENCIÓN DE LA PROFUNDIDAD
# ==========================================================

state = load_nmea_state()

updated_at = state.get("updated_at")
state_age = get_state_age(updated_at)

core_depth = get_core_depth(state)

state_is_fresh = (
    state_age is not None
    and state_age <= STALE_AFTER_SECONDS
)

if core_depth is not None and state_is_fresh:
    current_depth = core_depth
    depth_source = "PHASMIDA Core / NMEA"
else:
    current_depth = generate_fallback_depth(
        st.session_state.echo_sample_index
    )
    depth_source = "Simulación de respaldo"

st.session_state.echo_sample_index += 1

st.session_state.depth_history.append(
    current_depth
)

st.session_state.depth_source_history.append(
    depth_source
)

if len(st.session_state.depth_history) > WINDOW_SIZE:
    st.session_state.depth_history = (
        st.session_state.depth_history[-WINDOW_SIZE:]
    )

if len(st.session_state.depth_source_history) > WINDOW_SIZE:
    st.session_state.depth_source_history = (
        st.session_state.depth_source_history[-WINDOW_SIZE:]
    )


# ==========================================================
# DATOS DE VISUALIZACIÓN
# ==========================================================

depths = st.session_state.depth_history
sources = st.session_state.depth_source_history

sample_axis = list(range(len(depths)))

depth_df = pd.DataFrame({
    "Muestra": sample_axis,
    "Profundidad (m)": depths,
    "Fuente": sources
})

min_depth = min(depths)
max_depth = max(depths)
average_depth = float(np.mean(depths))

risk_level, risk_message = get_risk_level(
    current_depth
)


# ==========================================================
# CABECERA
# ==========================================================

st.title("Sonda de profundidad PHASMIDA")

st.caption(
    "Representación del perfil del fondo marino y de la "
    "profundidad bajo la quilla"
)

if core_depth is not None and state_is_fresh:
    st.success(
        "Sonda conectada correctamente a PHASMIDA Core."
    )

elif core_depth is None:
    st.info(
        "No se han recibido todavía sentencias DBT o DPT. "
        "Se utiliza una simulación de respaldo."
    )

else:
    st.warning(
        "El dato NMEA de profundidad está desactualizado. "
        "Se utiliza temporalmente la simulación de respaldo."
    )


# ==========================================================
# MÉTRICAS
# ==========================================================

col1, col2, col3, col4, col5, col6 = st.columns(6)

col1.metric(
    "Profundidad actual",
    f"{current_depth:.1f} m"
)

col2.metric(
    "Profundidad mínima",
    f"{min_depth:.1f} m"
)

col3.metric(
    "Profundidad máxima",
    f"{max_depth:.1f} m"
)

col4.metric(
    "Profundidad media",
    f"{average_depth:.1f} m"
)

col5.metric(
    "Estado",
    risk_level
)

col6.metric(
    "Hora UTC",
    datetime.now(timezone.utc).strftime("%H:%M:%S")
)


# ==========================================================
# MENSAJE DE RIESGO
# ==========================================================

if risk_level == "CRÍTICO":
    st.error(risk_message)

elif risk_level == "ALERTA":
    st.warning(risk_message)

else:
    st.success(risk_message)


# ==========================================================
# GRÁFICO DE SONDA
# ==========================================================

fig = go.Figure()


# Superficie del mar
fig.add_trace(
    go.Scatter(
        x=sample_axis,
        y=[0.0] * len(sample_axis),
        mode="lines",
        name="Superficie",
        line=dict(
            color=LIGHT_BLUE,
            width=3
        ),
        hovertemplate=(
            "Superficie del mar"
            "<extra></extra>"
        )
    )
)


# Columna de agua
fig.add_trace(
    go.Scatter(
        x=sample_axis,
        y=depths,
        mode="lines",
        name="Fondo marino",
        line=dict(
            color=PRIMARY_BLUE,
            width=3
        ),
        fill="tonexty",
        fillcolor="rgba(33, 150, 243, 0.20)",
        hovertemplate=(
            "Muestra: %{x}<br>"
            "Profundidad: %{y:.1f} m"
            "<extra></extra>"
        )
    )
)


# Línea de alerta
fig.add_trace(
    go.Scatter(
        x=sample_axis,
        y=[ALERT_DEPTH] * len(sample_axis),
        mode="lines",
        name=f"Alerta ({ALERT_DEPTH:.0f} m)",
        line=dict(
            color=ALERT_YELLOW,
            width=2,
            dash="dash"
        ),
        hovertemplate=(
            f"Umbral de alerta: {ALERT_DEPTH:.0f} m"
            "<extra></extra>"
        )
    )
)


# Línea crítica
fig.add_trace(
    go.Scatter(
        x=sample_axis,
        y=[CRITICAL_DEPTH] * len(sample_axis),
        mode="lines",
        name=f"Crítico ({CRITICAL_DEPTH:.0f} m)",
        line=dict(
            color=CRITICAL_RED,
            width=2,
            dash="dash"
        ),
        hovertemplate=(
            f"Umbral crítico: {CRITICAL_DEPTH:.0f} m"
            "<extra></extra>"
        )
    )
)


# Eco vertical actual
current_x = sample_axis[-1]

fig.add_trace(
    go.Scatter(
        x=[current_x, current_x],
        y=[0.0, current_depth],
        mode="lines",
        name="Eco actual",
        line=dict(
            color=PALE_BLUE,
            width=2,
            dash="dot"
        ),
        hovertemplate=(
            f"Lectura actual: {current_depth:.1f} m"
            "<extra></extra>"
        )
    )
)


# Punto de lectura actual
if risk_level == "CRÍTICO":
    current_point_color = CRITICAL_RED

elif risk_level == "ALERTA":
    current_point_color = ALERT_YELLOW

else:
    current_point_color = PALE_BLUE

fig.add_trace(
    go.Scatter(
        x=[current_x],
        y=[current_depth],
        mode="markers+text",
        text=[f"{current_depth:.1f} m"],
        textposition="top left",
        name="Lectura actual",
        marker=dict(
            color=current_point_color,
            size=12,
            line=dict(
                color=WHITE_BLUE,
                width=1
            )
        ),
        textfont=dict(
            color=current_point_color,
            size=14,
            family="Courier New"
        ),
        hovertemplate=(
            f"Profundidad actual: {current_depth:.1f} m"
            "<extra></extra>"
        )
    )
)


# Símbolo del buque
fig.add_annotation(
    x=current_x,
    y=-4,
    text="⛴",
    showarrow=False,
    font=dict(
        size=32,
        color=LIGHT_BLUE
    ),
    xanchor="center",
    yanchor="middle"
)

fig.add_annotation(
    x=current_x,
    y=-8,
    text="BUQUE",
    showarrow=False,
    font=dict(
        size=12,
        color=PALE_BLUE,
        family="Courier New"
    ),
    xanchor="center"
)


# ==========================================================
# ESTILO DEL GRÁFICO
# ==========================================================

fig.update_layout(
    template=None,
    paper_bgcolor=BACKGROUND_BLUE,
    plot_bgcolor=DEEP_BLUE,
    font=dict(
        color=PALE_BLUE,
        family="Courier New"
    ),
    xaxis=dict(
        title="Histórico de muestras",
        color=LIGHT_BLUE,
        gridcolor=GRID_BLUE,
        zeroline=False
    ),
    yaxis=dict(
        title="Profundidad (m)",
        color=LIGHT_BLUE,
        gridcolor=GRID_BLUE,
        range=[MAX_DEPTH, -12],
        zeroline=False
    ),
    height=650,
    margin=dict(
        l=40,
        r=40,
        t=40,
        b=40
    ),
    showlegend=True,
    legend=dict(
        bgcolor="rgba(2, 8, 23, 0.70)",
        bordercolor=DARK_BLUE,
        borderwidth=1,
        font=dict(
            color=PALE_BLUE
        )
    )
)

st.plotly_chart(
    fig,
    use_container_width=True,
    theme=None,
    key="phasmida_echo_sounder"
)


# ==========================================================
# INFORMACIÓN NMEA
# ==========================================================

st.subheader("Estado de la lectura")

info_col1, info_col2, info_col3, info_col4 = st.columns(4)

info_col1.metric(
    "Fuente",
    depth_source
)

info_col2.metric(
    "Última sentencia",
    state.get("last_sentence_type") or "N/D"
)

info_col3.metric(
    "Origen",
    state.get("source_ip") or "N/D"
)

info_col4.metric(
    "Edad del estado",
    (
        f"{state_age:.1f} s"
        if state_age is not None
        else "N/D"
    )
)


# ==========================================================
# TABLA
# ==========================================================

st.subheader("Datos recientes de profundidad")

st.dataframe(
    depth_df.tail(20),
    use_container_width=True,
    hide_index=True
)


# ==========================================================
# REFRESCO
# ==========================================================

time.sleep(REFRESH_SECONDS)
st.rerun()