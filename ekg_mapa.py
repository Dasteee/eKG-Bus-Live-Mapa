import requests
import json
import folium
import os
from datetime import datetime, timedelta
from folium.plugins import MarkerCluster, Search, Fullscreen, LocateControl
from jinja2 import Template
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REFRESH_SECONDS = 60
MAP_FILE = "kragujevac_busevi.html"
def get_vehicle_info(bus_id):
    bus_id_str = str(bus_id)
    if bus_id_str.startswith('30'):
        return "Strela Obrenovac", bus_id_str[2:]
    if bus_id_str.startswith('70'):
        return "Vulović Transport", bus_id_str[2:]
    return "Nepoznat prevoznik", bus_id_str
def get_secrets():
    api_url = os.getenv("API_URL")
    auth_token = os.getenv("AUTH_TOKEN")
    device_id = os.getenv("DEVICE_ID")
    if not all([api_url, auth_token, device_id]):
        raise ValueError("Nisu postavljene sve potrebne environment variables (API_URL, AUTH_TOKEN, DEVICE_ID)")
    headers = {
        'Authorization': f'Bearer {auth_token}',
        'X-Device-Id': device_id,
        'User-Agent': 'App/2 CFNetwork/3857.100.1 Darwin/25.0.0'
    }
    return api_url, headers

def get_clean_line_number(route_code):
    if not route_code or not isinstance(route_code, str):
        return "N/A"
    try:
        code_int = int(route_code)
        suburban_line = code_int % 1000
        if 600 <= suburban_line <= 613:
            return str(suburban_line)
        city_line = code_int % 100
        if 1 <= city_line <= 30: # Prošireno do 30 za svaki slučaj
            return str(city_line)
        if 1 <= code_int <= 30 or 600 <= code_int <= 613:
            return str(code_int)
        return route_code
    except (ValueError, TypeError):
        return route_code

def enhance_html_head(html_file, interval_seconds):
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        anti_cache_tags = f"""
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <meta http-equiv="refresh" content="{interval_seconds}">
"""
        if '<meta http-equiv="refresh"' not in html_content:
            html_content = html_content.replace('</head>', f'{anti_cache_tags}\n</head>')
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
    except Exception as e:
        print(f"Greška kod dodavanja HTML tagova: {e}")

def fetch_bus_data(api_url, headers):
    try:
        response = requests.get(api_url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        nested_data = json.loads(response.json()['data'])
        return nested_data['ROOT']['BUSES']['BUS']
    except Exception as e:
        print(f"Greška prilikom preuzimanja podataka: {e}")
        return None

def create_map(buses):
    if buses is None:
        buses = []

    kg_coords = [44.0141, 20.9116]
    bus_map = folium.Map(location=kg_coords, zoom_start=13, tiles="CartoDB dark_matter", max_zoom=21)

    # Dodaj slojeve mape
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', name='Satelit', attr='Esri').add_to(bus_map)
    folium.TileLayer('OpenStreetMap', name='Standardna mapa').add_to(bus_map)

    now = datetime.now()
    ten_min_ago = now - timedelta(minutes=10)
    sixty_min_ago = now - timedelta(minutes=60)
    archive_cutoff = datetime(2024, 1, 1)

    # 4 grupe
    fg_active = folium.FeatureGroup(name="🟢 Aktivna vozila", show=True)
    fg_mid = folium.FeatureGroup(name="🟡 10-60 min", show=True)
    fg_old = folium.FeatureGroup(name="🟠 60min-2024", show=False)
    fg_archive = folium.FeatureGroup(name="⚫ Arhiva", show=False)

    search_features = []
    counts = {'active': 0, 'mid': 0, 'old': 0, 'archive': 0, 'total': 0}

    for bus in buses:
        try:
            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S')
            lat = float(bus.get('LATITUDE', '0').replace(',', '.'))
            lon = float(bus.get('LONGITUDE', '0').replace(',', '.'))
            if lat == 0 or lon == 0:
                continue

            bus_id = bus.get('BUS_ID', 'N/A')
            route_code = bus.get('ROUTE_CODE', 'N/A')
            clean_line = get_clean_line_number(route_code)
            operator, internal_id = get_vehicle_info(bus_id)

            popup_html = f"""<b>Linija: {clean_line}</b> ({route_code})<br>
                             <b>Vozilo:</b> {bus_id}<br>
                             {operator} #{internal_id}<br>
                             <b>Poslednji signal:</b> {last_seen_dt.strftime('%d.%m.%Y. %H:%M:%S')}"""

            tooltip = f"Linija {clean_line} | {operator} #{internal_id}"

            icon = folium.Icon(color="gray", icon="bus", prefix="fa")

            # Odredi grupu i boju
            if last_seen_dt >= archive_cutoff:
                if last_seen_dt > ten_min_ago:
                    icon = folium.Icon(color="green", icon="bus", prefix="fa")
                    fg_active.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup_html, icon=icon))
                    counts['active'] += 1

                    # Za search
                    search_features.append({
                        'type': 'Feature',
                        'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                        'properties': {'BUS_ID': bus_id}
                    })
                elif last_seen_dt > sixty_min_ago:
                    icon = folium.Icon(color="orange", icon="bus", prefix="fa")
                    fg_mid.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup_html, icon=icon))
                    counts['mid'] += 1
                else:
                    icon = folium.Icon(color="lightgray", icon="bus", prefix="fa")
                    fg_old.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup_html, icon=icon))
                    counts['old'] += 1
            else:
                icon = folium.Icon(color="black", icon="bus", prefix="fa")
                fg_archive.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup_html, icon=icon))
                counts['archive'] += 1

            counts['total'] += 1
        except Exception:
            continue

    # Dodaj sve layer-e
    for fg in [fg_active, fg_mid, fg_old, fg_archive]:
        bus_map.add_child(fg)

    # Dodaj search layer
    if search_features:
        search_layer = folium.GeoJson(
            {'type': 'FeatureCollection', 'features': search_features},
            name="Pretraga",
            marker=folium.CircleMarker(radius=0, fill_opacity=0, opacity=0)
        )
        bus_map.add_child(search_layer)
        Search(
            layer=search_layer,
            geom_type='Point',
            placeholder='Traži garažni broj...',
            collapsed=True,
            search_label='BUS_ID',
            search_zoom=18
        ).add_to(bus_map)

    # LayerControl + fullscreen
    Fullscreen().add_to(bus_map)
    folium.LayerControl(collapsed=False).add_to(bus_map)

    # Statistika
    stats_html = f"""
    <div style="position: absolute; top: 10px; left: 50%; transform: translateX(-50%); 
                background-color: rgba(0,0,0,0.75); color: white; padding: 10px 15px; 
                border-radius: 8px; z-index: 999; font-size: 14px; min-width: 280px;">
        <b>Stanje na mapi</b><br>
        Ažurirano: {now.strftime('%d.%m.%Y. %H:%M:%S')}<br>
        Aktivna: {counts['active']}<br>
        10-60 min: {counts['mid']}<br>
        60min-2024: {counts['old']}<br>
        Arhiva: {counts['archive']}
    </div>
    """
    bus_map.get_root().html.add_child(folium.Element(stats_html))

    # Disclaimer
    disclaimer_html = """
    <div style="position: absolute; bottom: 10px; right: 10px; z-index: 999; background-color: rgba(30, 30, 30, 0.7); color: #ccc; padding: 5px 10px; border-radius: 5px; font-family: Arial, sans-serif; font-size: 11px; border: 1px solid #555;">
        <p style="margin: 0;"><b>Disclaimer:</b> Ovo je nezvanični, hobi projekat. Podaci su informativnog karaktera i moguće su netačnosti.</p>
    </div>
    """
    bus_map.get_root().html.add_child(folium.Element(disclaimer_html))

    # Save
    bus_map.save(MAP_FILE)
    enhance_html_head(MAP_FILE, REFRESH_SECONDS)
    print(f"✔️ Mapa uspešno generisana ({counts['total']} vozila).")



def main():
    api_url, headers = get_secrets()
    if not api_url or not headers:
        return
    buses = fetch_bus_data(api_url, headers)
    create_map(buses)

if __name__ == "__main__":
    main()