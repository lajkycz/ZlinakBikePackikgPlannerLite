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

# --- VLASTNÍ STYLOVÁNÍ (Šířka sidebaru a vzhled) ---
st.markdown(
    """
    <style>
    /* Rozšíření bočního panelu o cca 5-10% */
    [data-testid="stSidebar"] {
        min-width: 380px;
        max-width: 450px;
    }
    /* Úprava nadpisů v sidebaru pro lepší čitelnost */
    .stMarkdown em {
        color: #555;
        font-size: 0.9em;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🚲 Zlíňákův plánovač tras v1.0")

# --- POMOCNÉ FUNKCE ---
def get_village(lat, lon):
    try:
        geolocator = Nominatim(user_agent="zlinak_adventure_planner_web")
        time.sleep(1.1) 
        loc = geolocator.reverse((lat, lon), zoom=13, language="cs")
        if loc:
            a = loc.raw.get('address', {})
            return a.get('village') or a.get('town') or a.get('city') or a.get('municipality') or "Místo"
    except:
        return "Trasa"
    return "Místo"

# --- SIDEBAR: NASTAVENÍ A NAHRÁNÍ ---
with st.sidebar:
    st.header("⏱️ Časový harmonogram")
    st.markdown("*Nastavení časů pro začátek a konec vaší denní cesty. Pro správný výpočet vložte GPX soubor (např. z Mapy.cz).*")
    
    uploaded_file = st.file_uploader("Nahraj GPX soubor", type=["gpx"])
    
    col1, col2 = st.columns(2)
    with col1:
        start_h = st.selectbox("Hodina startu", [f"{i:02d}" for i in range(4, 13)], index=5, help="Zadej hodinu, kdy ráno vyrážíš na trasu.")
        end_h = st.selectbox("Hodina ukončení", [f"{i:02d}" for i in range(13, 24)], index=5, help="V kolik hodin chceš být nejpozději v cíli dne.")
    with col2:
        start_m = st.selectbox("Minuta startu", ["00", "15", "30", "45"])
        end_m = st.selectbox("Minuta ukončení", ["00", "15", "30", "45"])

    st.header("🚲 Výkon a odpočinek")
    speed = st.number_input("Průměrná rychlost (km/h)", value=18, 
                            help="Tvoje odhadovaná rychlost jízdy po rovině bez započtení pauz. Převýšení se dopočítává automaticky.")
    st.markdown("*Převýšení se dopočítává automaticky z GPX souboru.*")
    
    pause_str = st.selectbox("Doba pauzy během dne", 
                            ["0:00", "0:30", "1:00", "1:30", "2:00", "2:30", "3:00", "4:00"], index=5,
                            help="Celkový čas na jídlo, kávu a odpočinek. 2:30 je běžné pro pohodový výlet.")
    
    st.header("🗺️ Limitace")
    max_km = st.number_input("Maximální km za den (0 = bez limitu)", value=0,
                             help="Kolik maximálně chceš najet za den kilometrů?")

# --- HLAVNÍ LOGIKA VÝPOČTU ---
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
                    etapy.append({'pts': curr_pts, 'elevs': curr_elevs, 'dists': curr_dists, 'km': d_dnes, 'm': c_dnes, 'eta': eta, 'time': t_dnes})
                    curr_pts, curr_elevs, curr_dists, d_dnes, c_dnes, t_dnes = [[p2.latitude, p2.longitude]], [], [], 0, 0, 0

    if d_dnes > 0:
        eta = (datetime.strptime(f"{start_h}:{start_m}", "%H:%M") + timedelta(minutes=t_dnes + pauza_val)).strftime("%H:%M")
        etapy.append({'pts': curr_pts, 'elevs': curr_elevs, 'dists': curr_dists, 'km': d_dnes, 'm': c_dnes, 'eta': eta, 'time': t_dnes})

    # --- ZOBRAZENÍ VÝSLEDKŮ ---
    st.header("📊 Souhrnný itinerář")
    data = []
    for i, e in enumerate(etapy):
        data.append({"Den": f"Den {i+1}", "Vzdálenost": f"{e['km']:.1f} km", "Převýšení": f"{int(e['m'])} m", "Příjezd (ETA)": e['eta']})
    st.table(data)

    st.header("🗺️ Detailní itinerář etap")
    for i, e in enumerate(etapy):
        with st.expander(f"📍 Den {i+1}: Podrobnosti etapy", expanded=True):
            s_name = get_village(e['pts'][0][0], e['pts'][0][1])
            e_name = get_village(e['pts'][-1][0], e['pts'][-1][1])
            
            st.subheader(f"{s_name} ➔ {e_name}")
            st.write(f"⏱️ **Cíl:** {e['eta']} | 📏 **Délka:** {e['km']:.1f} km | 🏔️ **Nastoupáno:** {int(e['m'])} m")
            
            # --- MAPA (Větší výška a plná šířka) ---
            m = folium.Map(location=e['pts'][0], zoom_start=12)
            folium.PolyLine(e['pts'], color='#3498db', weight=5).add_to(m)
            folium.Marker(e['pts'][0], icon=folium.Icon(color='green', icon='play', prefix='fa')).add_to(m)
            folium.Marker(e['pts'][-1], icon=folium.Icon(color='red', icon='flag', prefix='fa')).add_to(m)
            m.fit_bounds(e['pts'])
            
            # Změna na výšku 600px pro lepší formát
            st_folium(m, use_container_width=True, height=600, returned_objects=[])
            
            # --- GRAF PROFILU ---
            fig, ax = plt.subplots(figsize=(10, 3))
            ax.fill_between(e['dists'], e['elevs'], color="#3498db", alpha=0.3)
            ax.plot(e['dists'], e['elevs'], color="#2980b9", linewidth=2)
            ax.set_ylabel("m n.m.")
            ax.set_xlabel("km")
            ax.grid(True, linestyle='--', alpha=0.5)
            st.pyplot(fig)
            
            # Průjezdní body
            cp1 = get_village(e['pts'][int(len(e['pts'])*0.33)][0], e['pts'][int(len(e['pts'])*0.33)][1])
            cp2 = get_village(e['pts'][int(len(e['pts'])*0.66)][0], e['pts'][int(len(e['pts'])*0.66)][1])
            st.info(f"🚩 **Trasa dne:** {s_name} ➔ {cp1} ➔ {cp2} ➔ {e_name}")

else:
    st.info("👈 Nahrajte svůj GPX soubor v levém panelu pro vygenerování itineráře dle etap.")