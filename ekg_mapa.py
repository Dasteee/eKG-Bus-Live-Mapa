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
    
    # Add tile layers
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', name='Satelit', attr='Esri', max_zoom=21).add_to(bus_map)
    folium.TileLayer('OpenStreetMap', name='Standardna mapa').add_to(bus_map)

    # Define time thresholds
    now = datetime.now()
    ten_minutes_ago = now - timedelta(minutes=10)
    one_hour_ago = now - timedelta(minutes=60)
    archive_cutoff = datetime(2024, 1, 1)

    # Define groups
    active_group = folium.FeatureGroup(name="Aktivna vozila", show=True).add_to(bus_map)
    mid_delay_group = folium.FeatureGroup(name="Aktivna Vozila (10 - 60 min)", show=True).add_to(bus_map)
    old_group = folium.FeatureGroup(name="Neaktivna Vozila", show=False).add_to(bus_map)
    archive_group = folium.FeatureGroup(name="Arhiva (pre 2024)", show=False).add_to(bus_map)

    search_features = []
    counts = {'active': 0, 'mid': 0, 'old': 0, 'archive': 0, 'total': 0}

    for bus in buses:
        try:
            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S')
            lat = float(bus.get('LATITUDE', '0').replace(',', '.'))
            lon = float(bus.get('LONGITUDE', '0').replace(',', '.'))
            if lat == 0 and lon == 0:
                continue

            bus_id = bus.get('BUS_ID', 'N/A')
            route_code = bus.get('ROUTE_CODE', 'N/A')
            clean_line = get_clean_line_number(route_code)

            popup_html = f"<b>Linija: {clean_line}</b> ({route_code})<br><b>Vozilo:</b> {bus_id}<br>{get_vehicle_info(bus_id)}<br><b>Poslednji signal:</b> {last_seen_dt.strftime('%d.%m.%Y. %H:%M:%S')}"
            tooltip = f"Linija {clean_line} | {get_vehicle_info(bus_id)}"

            marker = folium.Marker(location=[lat, lon], popup=popup_html, tooltip=tooltip)

            if last_seen_dt < archive_cutoff:
                marker.icon = folium.Icon(color='black', prefix='fa', icon='bus')
                marker.add_to(archive_group)
                counts['archive'] += 1
            elif last_seen_dt > ten_minutes_ago:
                marker.icon = folium.Icon(color='green', prefix='fa', icon='bus')
                marker.add_to(active_group)
                counts['active'] += 1
                search_features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                    'properties': {'BUS_ID': bus_id}
                })
            elif ten_minutes_ago >= last_seen_dt > one_hour_ago:
                marker.icon = folium.Icon(color='orange', prefix='fa', icon='bus')
                marker.add_to(mid_delay_group)
                counts['mid'] += 1
            elif one_hour_ago >= last_seen_dt >= archive_cutoff:
                marker.icon = folium.Icon(color='lightgray', prefix='fa', icon='bus')
                marker.add_to(old_group)
                counts['old'] += 1

            counts['total'] += 1
        except Exception:
            continue

    # Stats box
    stats_html = f"""
    <div id="stats-box" style="position: absolute; top: 10px; left: 50%; transform: translateX(-50%); z-index: 999; background-color: rgba(30, 30, 30, 0.85); color: #f0f0f0; padding: 10px 15px; border-radius: 8px; font-family: Arial, sans-serif; font-size: 14px; border: 1px solid #555; backdrop-filter: blur(5px); -webkit-backdrop-filter: blur(5px); box-shadow: 0 4px 12px rgba(0,0,0,0.5); min-width: 280px;">
        <span onclick="this.parentElement.style.display='none';" style="position: absolute; top: 2px; right: 8px; cursor: pointer; font-size: 24px; color: #aaa; font-weight: bold;">&times;</span>
        <h4 style="margin: 0 0 10px 0; padding-bottom: 5px; border-bottom: 1px solid #666; font-size: 16px; text-align: center;">Stanje na mapi</h4>
        <p style="margin: 5px 0;">Ažurirano: <strong>{now.strftime('%d.%m.%Y. %H:%M:%S')}</strong></p>
        <p style="margin: 5px 0;">Aktivna: <strong>{counts['active']}</strong></p>
        <p style="margin: 5px 0;">10-60 min: <strong>{counts['mid']}</strong></p>
        <p style="margin: 5px 0;">60min-2024: <strong>{counts['old']}</strong></p>
        <p style="margin: 5px 0;">Arhiva: <strong>{counts['archive']}</strong></p>
    </div>
    """
    bus_map.get_root().html.add_child(folium.Element(stats_html))

    disclaimer_html = """
    <div style="position: absolute; bottom: 10px; right: 10px; z-index: 999; background-color: rgba(30, 30, 30, 0.7); color: #ccc; padding: 5px 10px; border-radius: 5px; font-family: Arial, sans-serif; font-size: 11px; border: 1px solid #555;">
        <p style="margin: 0;"><b>Disclaimer:</b> Ovo je nezvanični, hobi projekat. Podaci su informativnog karaktera i moguće su netačnosti.</p>
    </div>
    """
    bus_map.get_root().html.add_child(folium.Element(disclaimer_html))

    # Search feature (only for active vehicles)
    if search_features:
        search_layer = folium.GeoJson({
            'type': 'FeatureCollection',
            'features': search_features
        }, marker=folium.CircleMarker(radius=0, opacity=0), name='SearchLayer').add_to(bus_map)

        Search(
            layer=search_layer,
            geom_type='Point',
            placeholder='Traži garažni broj...',
            collapsed=True,
            search_label='BUS_ID',
            search_zoom=19,
            initial=False
        ).add_to(bus_map)

    Fullscreen().add_to(bus_map)
    folium.LayerControl(collapsed=True).add_to(bus_map)
    bus_map.save(MAP_FILE)
    enhance_html_head(MAP_FILE, REFRESH_SECONDS)
    print(f"Mapa uspešno generisana: {counts['total']} ukupno, {counts['active']} aktivnih.")


def main():
    api_url, headers = get_secrets()
    if not api_url or not headers:
        return
    buses = fetch_bus_data(api_url, headers)
    create_map(buses)

if __name__ == "__main__":
    main()