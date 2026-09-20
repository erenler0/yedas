"""Ana ekran: canlı YEDAŞ kesintileri, poligon eşleştirme, harita."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src import db
from src.maps import outage_map
from src.reports import affected_outages_jpg
from src.services import filter_window, load_sites_cached, load_yedas_cached, persist_and_match
from src.utils import duration_hours, fmt_dt, from_iso


def render() -> None:
    st.subheader("YEDAŞ canlı planlı kesintiler")
    sites = load_sites_cached()
    if not sites:
        st.info("Henüz saha yüklenmedi. Admin panelinden Excel senkronu yapın.")
        return

    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        window = st.radio("Zaman filtresi", ["Günlük", "3 Günlük", "7 Günlük"], horizontal=True)
    days = {"Günlük": 1, "3 Günlük": 3, "7 Günlük": 7}[window]

    try:
        outages = load_yedas_cached()
    except Exception as exc:
        st.error(f"YEDAŞ API şu an okunamadı: {exc}")
        stored = db.list_outages()
        if not stored:
            return
        st.warning("Veritabanındaki son kesinti anlık görüntüsü gösteriliyor.")
        outages = stored
        for o in outages:
            o["start_dt"] = from_iso(o.get("start_at"))
            o["end_dt"] = from_iso(o.get("end_at"))
            import json

            o["coords"] = json.loads(o.get("coords_json") or "[]")
            o["address"] = json.loads(o.get("address_json") or "[]")
            o["geojson"] = json.loads(o.get("geojson_json") or "{}")

    # Kritik performans noktası: API yüzlerce kayıt döndürse bile yalnızca seçilen
    # gün penceresindeki kesintiler Shapely eşleştirmesine girer.
    window_outages = filter_window(outages, days)
    matched = persist_and_match(window_outages, sites)
    visible = filter_window(matched, days)

    affected_n = sum(len(i.get("affected") or []) for i in visible)
    with col_f2:
        st.metric("Kesinti kaydı", len(visible))
    with col_f3:
        st.metric("Etkilenen saha (çakışma)", affected_n)

    st.caption("Kırmızı pin: YEDAŞ kesinti poligonu ile Point-in-Polygon çakışan saha. Mavi pin: poligon merkezine 15 km içindeki etkilenmeyen saha.")
    fmap = outage_map(visible, show_nearby=True)
    st_folium(fmap, width=None, height=560, returned_objects=[], use_container_width=True)

    # Yalnızca poligonla çakışan sahalar detay listesine girer.
    rows = []
    for item in visible:
        start = item.get("start_dt") or from_iso(item.get("start_at"))
        end = item.get("end_dt") or from_iso(item.get("end_at"))
        duration = duration_hours(start, end) if isinstance(start, datetime) else None
        for site in item.get("affected") or []:
            rows.append({
                "Saha": site.get("name"),
                "İl": site.get("il"),
                "İlçe": site.get("ilce"),
                "Mahalle": site.get("mahalle"),
                "Adres": " / ".join([p for p in [site.get("il"), site.get("ilce"), site.get("mahalle")] if p]) or "—",
                "Tarih": fmt_dt(start) if isinstance(start, datetime) else (item.get("start_at") or "—"),
                "Kesinti Süresi": f"{duration:.1f} saat" if duration is not None else "—",
                "Nedeni": item.get("details") or item.get("title") or "—",
            })

    if not rows:
        st.success("Seçilen pencerede kesinti poligonuyla çakışan saha yok.")
        return

    df = pd.DataFrame(rows)

    st.markdown("### Kesinti detayları")
    f1, f2 = st.columns(2)
    with f1:
        provinces = ["Tümü"] + sorted([str(x) for x in df["İl"].dropna().unique() if str(x).strip()])
        selected_province = st.selectbox("İl", provinces, key="home_outage_province")
    filtered = df if selected_province == "Tümü" else df[df["İl"] == selected_province]
    with f2:
        districts = ["Tümü"] + sorted([str(x) for x in filtered["İlçe"].dropna().unique() if str(x).strip()])
        selected_district = st.selectbox("İlçe", districts, key="home_outage_district")
    if selected_district != "Tümü":
        filtered = filtered[filtered["İlçe"] == selected_district]

    detail_columns = ["Saha", "Adres", "Tarih", "Kesinti Süresi", "Nedeni"]
    st.dataframe(filtered[detail_columns], use_container_width=True, hide_index=True)
    st.caption(f"Gösterilen saha: {len(filtered)} / {len(df)}")

    jpg = affected_outages_jpg(filtered.to_dict("records"), selected_province, selected_district)
    st.download_button(
        "Kesinti çıktısını JPG indir",
        data=jpg,
        file_name="yedas_kesinti_ciktisi.jpg",
        mime="image/jpeg",
    )
