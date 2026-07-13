import json
import os
import random
from datetime import datetime, timezone

import folium
import pandas as pd
import streamlit as st
from folium.features import DivIcon
from streamlit_folium import st_folium


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

STATE_FILE = os.getenv(
    "PHASMIDA_STATE_FILE",
    "events/nmea_state.json"
)

DEFAULT_SHIP = {
    "name": "Kontiki",
    "lat": 38.335,
    "lon": -0.430,
    "heading": 75.0,
    "course": 75.0,
    "speed": 10.5,
    "updated_at": None,
    "source_ip": None,
    "sentence_type": None
}

MAP_ZOOM = 14
MAX_TRACK_POINTS = 500
STALE_AFTER_SECONDS = 10


# ==========================================================
# LECTURA DEL ESTADO PHASMIDA CORE
# ==========================================================

def load_nmea_state() -> dict:
    """Carga el estado de navegación generado por PHASMIDA Core."""

    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            state = json.load(file)

        return state if isinstance(state, dict) else {}

    except (OSError, json.JSONDecodeError):
        return {}


def build_own_ship(state: dict) -> dict:
    """Construye el estado del buque propio."""

    position = state.get("position", {})
    navigation = state.get("navigation", {})

    latitude = position.get("latitude")
    longitude = position.get("longitude")

    heading = navigation.get("heading_deg")
    course = navigation.get("course_deg")
    speed = navigation.get("speed_knots")

    resolved_heading = (
        float(heading)
        if heading is not None
        else float(course)
        if course is not None
        else DEFAULT_SHIP["heading"]
    )

    resolved_course = (
        float(course)
        if course is not None
        else float(heading)
        if heading is not None
        else DEFAULT_SHIP["course"]
    )

    return {
        "name": DEFAULT_SHIP["name"],
        "lat": (
            float(latitude)
            if latitude is not None
            else DEFAULT_SHIP["lat"]
        ),
        "lon": (
            float(longitude)
            if longitude is not None
            else DEFAULT_SHIP["lon"]
        ),
        "heading": resolved_heading,
        "course": resolved_course,
        "speed": (
            float(speed)
            if speed is not None
            else DEFAULT_SHIP["speed"]
        ),
        "updated_at": state.get("updated_at"),
        "source_ip": state.get("source_ip"),
        "sentence_type": state.get("last_sentence_type")
    }


def build_track_points(state: dict) -> list[list[float]]:
    """Extrae la derrota registrada por PHASMIDA Core."""

    track_points: list[list[float]] = []
    raw_track = state.get("track", [])

    if not isinstance(raw_track, list):
        return track_points

    for point in raw_track[-MAX_TRACK_POINTS:]:
        if not isinstance(point, dict):
            continue

        latitude = point.get("lat")
        longitude = point.get("lon")

        if latitude is None or longitude is None:
            continue

        try:
            track_points.append([
                float(latitude),
                float(longitude)
            ])
        except (TypeError, ValueError):
            continue

    return track_points


def get_state_age(updated_at: str | None) -> float | None:
    """Calcula la antigüedad del estado en segundos."""

    if not updated_at:
        return None

    try:
        state_time = datetime.fromisoformat(updated_at)
        now = datetime.now(timezone.utc)

        return abs((now - state_time).total_seconds())

    except (TypeError, ValueError):
        return None


# ==========================================================
# AIS SIMULADO ESTABLE
# ==========================================================

def generate_ais_targets() -> list[dict]:
    """Genera blancos AIS que permanecen estables entre refrescos."""

    targets = []

    for index in range(6):
        targets.append({
            "mmsi": f"224000{index + 1}",
            "name": f"AIS_TARGET_{index + 1}",
            "lat": 38.30 + random.uniform(-0.05, 0.09),
            "lon": -0.42 + random.uniform(-0.08, 0.12),
            "speed": round(random.uniform(3, 18), 1),
            "course": round(random.uniform(0, 359), 1),
            "status": random.choice([
                "normal",
                "normal",
                "sospechoso"
            ])
        })

    return targets


if "ais_targets" not in st.session_state:
    st.session_state.ais_targets = generate_ais_targets()


# ==========================================================
# ICONO ORIENTADO DEL BUQUE
# ==========================================================

def create_ship_icon(heading: float) -> DivIcon:
    """Crea un símbolo triangular orientado según el rumbo."""

    heading = float(heading) % 360.0

    html = f"""
    <div style="
        width: 34px;
        height: 34px;
        transform: rotate({heading}deg);
        transform-origin: center center;
        display: flex;
        align-items: center;
        justify-content: center;
    ">
        <div style="
            width: 0;
            height: 0;
            border-left: 10px solid transparent;
            border-right: 10px solid transparent;
            border-bottom: 27px solid #0d47a1;
            filter:
                drop-shadow(0 0 2px white)
                drop-shadow(0 0 3px #0d47a1);
        ">
        </div>
    </div>
    """

    return DivIcon(
        html=html,
        icon_size=(34, 34),
        icon_anchor=(17, 17)
    )


# ==========================================================
# INTERFAZ
# ==========================================================

st.set_page_config(
    page_title="ECDIS PHASMIDA",
    layout="wide"
)

st.title("ECDIS simulado")

st.caption(
    "Sistema de Información y Visualización de Cartas Electrónicas"
)

st.caption(
    "Posición, velocidad, rumbo y derrota obtenidos "
    "desde PHASMIDA Core"
)

state = load_nmea_state()
own_ship = build_own_ship(state)
track_points = build_track_points(state)
state_age = get_state_age(own_ship["updated_at"])

df_ais = pd.DataFrame(st.session_state.ais_targets)


# ==========================================================
# ESTADO DE LA CONEXIÓN
# ==========================================================

if not state:
    st.warning(
        "No se ha encontrado el estado NMEA compartido. "
        "Se muestran valores de respaldo."
    )

elif state_age is None or state_age > STALE_AFTER_SECONDS:
    st.warning(
        "El estado NMEA no se ha actualizado recientemente. "
        "La visualización puede contener datos antiguos."
    )

else:
    st.success(
        "ECDIS conectado correctamente a PHASMIDA Core."
    )


# ==========================================================
# MÉTRICAS
# ==========================================================

col1, col2, col3, col4, col5, col6 = st.columns(6)

col1.metric(
    "Buque propio",
    own_ship["name"]
)

col2.metric(
    "Velocidad",
    f"{own_ship['speed']:.1f} kn"
)

col3.metric(
    "Rumbo",
    f"{own_ship['heading']:.1f}º"
)

col4.metric(
    "Curso",
    f"{own_ship['course']:.1f}º"
)

col5.metric(
    "Puntos de derrota",
    len(track_points)
)

col6.metric(
    "Edad del estado",
    (
        f"{state_age:.1f} s"
        if state_age is not None
        else "N/D"
    )
)


# ==========================================================
# MAPA
# ==========================================================

m = folium.Map(
    location=[
        own_ship["lat"],
        own_ship["lon"]
    ],
    zoom_start=MAP_ZOOM,
    tiles="OpenStreetMap",
    control_scale=True
)

folium.TileLayer(
    tiles="https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png",
    attr="OpenSeaMap",
    name="Seamarks",
    overlay=True,
    control=True
).add_to(m)


# ==========================================================
# DERROTA REAL DEL BUQUE
# ==========================================================

if len(track_points) >= 2:
    folium.PolyLine(
        track_points,
        color="#1565c0",
        weight=4,
        opacity=0.9,
        tooltip="Derrota NMEA registrada"
    ).add_to(m)

# Último punto de la derrota
if track_points:
    folium.CircleMarker(
        location=track_points[-1],
        radius=5,
        color="#ff9800",
        fill=True,
        fill_color="#ff9800",
        fill_opacity=1.0,
        tooltip="Última posición NMEA"
    ).add_to(m)


# ==========================================================
# BUQUE PROPIO
# ==========================================================

folium.Marker(
    location=[
        own_ship["lat"],
        own_ship["lon"]
    ],
    popup=(
        f"<b>{own_ship['name']}</b><br>"
        f"Latitud: {own_ship['lat']:.6f}<br>"
        f"Longitud: {own_ship['lon']:.6f}<br>"
        f"Rumbo: {own_ship['heading']:.1f}º<br>"
        f"Curso: {own_ship['course']:.1f}º<br>"
        f"Velocidad: {own_ship['speed']:.1f} kn<br>"
        f"Fuente: {own_ship['source_ip'] or 'desconocida'}<br>"
        f"Última sentencia: "
        f"{own_ship['sentence_type'] or 'desconocida'}"
    ),
    tooltip="Buque propio",
    icon=create_ship_icon(
        own_ship["heading"]
    )
).add_to(m)


# ==========================================================
# BLANCOS AIS SIMULADOS
# ==========================================================

for _, row in df_ais.iterrows():
    color = (
        "red"
        if row["status"] == "sospechoso"
        else "green"
    )

    folium.Marker(
        location=[
            row["lat"],
            row["lon"]
        ],
        popup=(
            f"<b>{row['name']}</b><br>"
            f"MMSI: {row['mmsi']}<br>"
            f"Velocidad: {row['speed']} kn<br>"
            f"Curso: {row['course']}º<br>"
            f"Estado: {row['status']}"
        ),
        tooltip=row["name"],
        icon=folium.Icon(
            color=color,
            icon="location-dot",
            prefix="fa"
        )
    ).add_to(m)


# ==========================================================
# ZONA DE ALERTA
# ==========================================================

folium.Circle(
    location=[
        own_ship["lat"] + 0.020,
        own_ship["lon"] + 0.065
    ],
    radius=2500,
    color="red",
    fill=True,
    fill_opacity=0.15,
    tooltip="Zona de alerta"
).add_to(m)

folium.LayerControl().add_to(m)


# No se utiliza fit_bounds():
# el zoom permanece fijo y el mapa sigue al buque.

st_folium(
    m,
    width=None,
    height=650,
    key="phasmida_ecdis_map"
)


# ==========================================================
# ESTADO NMEA
# ==========================================================

st.subheader("Estado NMEA del buque")

state_table = pd.DataFrame([
    {
        "Parámetro": "Latitud",
        "Valor": f"{own_ship['lat']:.6f}"
    },
    {
        "Parámetro": "Longitud",
        "Valor": f"{own_ship['lon']:.6f}"
    },
    {
        "Parámetro": "Velocidad",
        "Valor": f"{own_ship['speed']:.1f} kn"
    },
    {
        "Parámetro": "Curso",
        "Valor": f"{own_ship['course']:.1f}º"
    },
    {
        "Parámetro": "Rumbo",
        "Valor": f"{own_ship['heading']:.1f}º"
    },
    {
        "Parámetro": "Puntos de derrota",
        "Valor": len(track_points)
    },
    {
        "Parámetro": "Última sentencia",
        "Valor": own_ship["sentence_type"] or "N/D"
    },
    {
        "Parámetro": "Fuente",
        "Valor": own_ship["source_ip"] or "N/D"
    },
    {
        "Parámetro": "Actualización",
        "Valor": own_ship["updated_at"] or "N/D"
    }
])

st.dataframe(
    state_table,
    use_container_width=True,
    hide_index=True
)


# ==========================================================
# BLANCOS AIS
# ==========================================================

st.subheader("Blancos AIS simulados")

st.dataframe(
    df_ais,
    use_container_width=True,
    hide_index=True
)
