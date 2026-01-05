import streamlit as st
import gpxpy
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
import time

# --- KONFIGURACE STRÁNKY ---
st.set_page_config(page_title="Zlíňákův plánovač", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] { min-width: 380px; max-width: 450px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚲 Zlíňákův plánovač tras v1.6")

# --- POMOCNÉ FUNKCE ---
def get_village(lat, lon):
    try:
        geolocator = Nominatim(user_agent="zlinak_adventure_planner_v3")
        time.sleep(1.1) 
        loc = geolocator.reverse((lat, lon), zoom=13, language="cs")
        if loc:
            a = loc.raw.get('address', {})
            return a.get('village') or a.get('town') or a.get('city') or a.get('municipality') or "Místo"
    except:
        return "..."
    return "..."

# --- SIDEBAR ---
with st.sidebar:
    st.header("⏱️ Časový harmonogram")
    uploaded_file = st.file_uploader("Nahraj GPX soubor", type=["gpx"])
    
    col1, col2 = st.columns(2)
    with col1:
        start_h = st.selectbox("Hodina startu", [f"{i:02d}" for i in range(4, 13)], index=5)
        end_h = st.selectbox("Hodina ukončení", [f"{i:02d}" for i in range(13, 24)], index=5)
    with col2:
        start_m = st.selectbox("Minuta startu", ["00", "15", "30", "45"])
        end_m = st.selectbox("Minuta ukončení", ["00", "15", "30", "45"])

    st.header("🚲 Výkon a odpočinek")
    speed = st.number_input("Průměrná rychlost (km/h)", value=18)
    pause_str = st.selectbox("Doba pauzy během dne", ["0:00", "0:30", "1:00", "1:30", "2:00", "2:30", "3:00", "4:00"], index=5)
    
    st.header("🗺️ Limitace")
    max_km = st.number_input("Maximální km za den (0 = bez limitu)", value=0)

# --- VÝPOČTY ---
if uploaded_file is not None:
    gpx = gpxpy.parse(uploaded_file)
    p_h, p_m = map(int, pause_str.split(':'))
    pauza_val = p_h * 60 + p_m
    limit_jizdy = (int(end_h)*60 + int(end_m)) - (int(start_h)*60 + int(start_m)) - pauza_val
    
    etapy, curr_pts, curr_elevs, curr_dists, d_dnes, c_dnes, t_dnes = [], [], [], [], 0, 0, 0
    
    for track in gpx.tracks:
        for segment in track.segments:
            for i in range(len(segment.points) - 1):
                p1, p2 = segment.points[i], segment.points[i+1]
                dist = p1.distance_2d(p2) / 1000
                elev = max(0, p2.elevation - p1.elevation) if p2.elevation and p1.elevation else 0
                t_seg = (dist / speed) * 60 + ((elev / 100) * 10 if elev > 0 else 0)
                
                curr_pts.append([p1.latitude, p1.longitude])
                curr_elevs.append(p1.elevation or 0)
                curr_dists.append(d_dnes)
                d_dnes += dist
                c_dnes += elev
                t_dnes += t_seg

                if t_dnes >= limit_jizdy or (max_km > 0 and d_dnes >= max_km):
                    eta = (datetime.strptime(f"{start_h}:{start_m}", "%H:%M") + timedelta(minutes=t_dnes + pauza_val)).strftime("%H:%M")
                    etapy.append({'pts': curr_pts, 'elevs': curr_elevs, 'dists': curr_dists, 'km': d_dnes, 'm': c_dnes, 'eta': eta})
                    curr_pts, curr_elevs, curr_dists, d_dnes, c_dnes, t_dnes = [[p2.latitude, p2.longitude]], [], [], 0, 0, 0

    if d_dnes > 0:
        eta = (datetime.strptime(f"{start_h}:{start_m}", "%H:%M") + timedelta(minutes=t_dnes + pauza_val)).strftime("%H:%M")
        etapy.append({'pts': curr_pts, 'elevs': curr_elevs, 'dists': curr_dists, 'km': d_dnes, 'm': c_dnes, 'eta': eta})

    st.header("📊 Souhrnný itinerář")
    data = [{"Den": f"Den {i+1}", "Vzdálenost": f"{e['km']:.1f} km", "Převýšení": f"{int(e['m'])} m", "Příjezd (ETA)": e['eta']} for i, e in enumerate(etapy)]
    st.table(data)

    st.header("🗺️ Detailní itinerář etap")
    for i, e in enumerate(etapy):
        with st.expander(f"📍 Den {i+1}: Podrobnosti etapy", expanded=True):
            # 1. ZÍSKÁNÍ NÁZVŮ (START, CÍL, PRŮJEZD)
            s_name = get_village(e['pts'][0][0], e['pts'][0][1])
            e_name = get_village(e['pts'][-1][0], e['pts'][-1][1])
            
            num_pts = len(e['pts'])
            mid_towns = []
            if num_pts > 10:
                indices = [int(1 + (num_pts - 2) * j / 7) for j in range(8)]
                for idx in indices:
                    t = get_village(e['pts'][idx][0], e['pts'][idx][1])
                    if t != s_name and t != e_name and (not mid_towns or t != mid_towns[-1]):
                        mid_towns.append(t)
            
            # 2. TEXTOVÉ INFORMACE NAHORU
            st.subheader(f"{s_name} ➔ {e_name}")
            
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.markdown(f"**📏 Délka:** {e['km']:.1f} km")
                st.markdown(f"**⛰️ Převýšení:** {int(e['m'])} m")
            with col_info2:
                st.markdown(f"**🏁 Předpokládaný dojezd:** {e['eta']}")

            route_str = " → ".join(mid_towns) if mid_towns else "Přímá trasa"
            st.info(f"🏘️ **Průjezdní obce:** {route_str}")
            
            # 3. MAPA
            m = folium.Map(location=e['pts'][0], zoom_start=12)
            folium.PolyLine(e['pts'], color='#3498db', weight=5, opacity=0.8).add_to(m)
            folium.Marker(e['pts'][0], icon=folium.Icon(color='green', icon='play', prefix='fa')).add_to(m)
            folium.Marker(e['pts'][-1], icon=folium.Icon(color='red', icon='flag', prefix='fa')).add_to(m)
            m.fit_bounds(e['pts'])
            st_folium(m, use_container_width=True, height=750, returned_objects=[])
            
            # 4. GRAF PROFILU
            fig, ax = plt.subplots(figsize=(10, 1.35))
            ax.fill_between(e['dists'], e['elevs'], color="#3498db", alpha=0.2)
            ax.plot(e['dists'], e['elevs'], color="#2980b9", linewidth=1.5)
            plt.tight_layout()
            ax.set_ylabel("m n.m.", fontsize=8)
            ax.tick_params(axis='both', which='major', labelsize=8)
            ax.grid(True, linestyle='--', alpha=0.2)
            st.pyplot(fig)

else:
    st.info("👈 Nahrajte svůj GPX soubor v levém panelu.")