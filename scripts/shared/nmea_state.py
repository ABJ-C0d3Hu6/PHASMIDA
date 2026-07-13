import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


STATE_FILE = os.getenv(
    "PHASMIDA_STATE_FILE",
    "events/nmea_state.json"
)

DEFAULT_STATE: dict[str, Any] = {
    "updated_at": None,
    "source_ip": None,
    "last_sentence": None,
    "last_sentence_type": None,
    "last_talker_id": None,
    "position": {
        "latitude": None,
        "longitude": None,
        "altitude_m": None
    },
    "navigation": {
        "speed_knots": None,
        "course_deg": None,
        "heading_deg": None
    },
    "depth": {
        "meters": None
    },
    "engine": {
        "rpm": None
    },
    "track": [],
    "security": {
        "suspicious": False,
        "alerts": []
    }
}


def ensure_state_directory() -> None:
    directory = os.path.dirname(STATE_FILE)

    if directory:
        os.makedirs(directory, exist_ok=True)


def read_state() -> dict[str, Any]:
    ensure_state_directory()

    if not os.path.exists(STATE_FILE):
        return deepcopy(DEFAULT_STATE)

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return deepcopy(DEFAULT_STATE)

        # Completa claves nuevas si el archivo procede
        # de una versión anterior del estado.
        state = deepcopy(DEFAULT_STATE)

        for key, value in data.items():
            if (
                key in state
                and isinstance(state[key], dict)
                and isinstance(value, dict)
            ):
                state[key].update(value)
            else:
                state[key] = value

        return state

    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_STATE)


def write_state(state: dict[str, Any]) -> None:
    ensure_state_directory()

    directory = os.path.dirname(STATE_FILE) or "."

    file_descriptor, temporary_path = tempfile.mkstemp(
        dir=directory,
        prefix=".nmea_state_",
        suffix=".json"
    )

    try:
        with os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                state,
                file,
                ensure_ascii=False,
                indent=2
            )

        os.replace(
            temporary_path,
            STATE_FILE
        )

    except Exception:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

        raise


def update_state(
    updates: dict[str, Any],
    source_ip: str | None = None,
    sentence: str | None = None,
    sentence_type: str | None = None,
    talker_id: str | None = None,
    suspicious: bool | None = None,
    alerts: list[str] | None = None
) -> dict[str, Any]:
    state = read_state()

    for section, values in updates.items():
        if (
            section in state
            and isinstance(state[section], dict)
            and isinstance(values, dict)
        ):
            state[section].update(values)
        else:
            state[section] = values

    state["updated_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    if source_ip is not None:
        state["source_ip"] = source_ip

    if sentence is not None:
        state["last_sentence"] = sentence

    if sentence_type is not None:
        state["last_sentence_type"] = sentence_type

    if talker_id is not None:
        state["last_talker_id"] = talker_id

    if suspicious is not None:
        state["security"]["suspicious"] = suspicious

    if alerts is not None:
        state["security"]["alerts"] = alerts

    position = state.get("position", {})
    latitude = position.get("latitude")
    longitude = position.get("longitude")

    if latitude is not None and longitude is not None:
        track = state.setdefault("track", [])

        new_point = {
            "lat": float(latitude),
            "lon": float(longitude),
            "timestamp": state["updated_at"]
        }

        if not track:
            track.append(new_point)
        else:
            last_point = track[-1]

            if (
                last_point.get("lat") != new_point["lat"]
                or last_point.get("lon") != new_point["lon"]
            ):
                track.append(new_point)

        state["track"] = track[-500:]

    write_state(state)

    return state