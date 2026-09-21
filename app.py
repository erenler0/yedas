"""YEDAŞ × GSM planlı kesinti izleme — Streamlit giriş noktası."""

from __future__ import annotations

import os
import sys
import urllib3

# Şirket firewall SSL doğrulamalarından kaynaklanan uyarıları kapatır
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Streamlit'in dış internete (streamlit.io) telemetry/istatistik göndermesini engeller
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import streamlit as st

from src.db import init_db
from ui import admin, analysis, faults, home, sites_map
from ui.styles import inject

st.set_page_config(
    page_title="YEDAŞ × GSM Kesinti",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
inject()

st.sidebar.title("YEDAŞ × GSM")
st.sidebar.caption("Planlı kesinti · Point-in-Polygon · OSRM")
page = st.sidebar.radio(
    "Ekran",
    [
        "📡 Ana ekran",
        "📊 Detay ve analiz",
        "🗺️ Sahalar ve mesafe",
        "🚨 Arıza takip",
        "🔐 Admin",
    ],
)

if page == "📡 Ana ekran":
    home.render()
elif page == "📊 Detay ve analiz":
    analysis.render()
elif page == "🗺️ Sahalar ve mesafe":
    sites_map.render()
elif page == "🚨 Arıza takip":
    faults.render()
else:
    admin.render()
