import requests
import json
import folium
import os
from datetime import datetime, timedelta
from folium.plugins import MarkerCluster, Search, Fullscreen, LocateControl
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REFRESH_SECONDS = 600
MAP_FILE = "kragujevac_busevi.html"

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

def get_vehicle_info(bus_id):
    bus_id_str = str(bus_id)
    if bus_id_str.startswith('30'):
        return "Strela Obrenovac", bus_id_str[2:]
    if bus_id_str.startswith('70'):
        return "Vulović Transport", bus_id_str[2:]
    return "Nepoznat prevoznik", bus_id_str

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
        print(f"!!! GREŠKA prilikom preuzimanja ili parsiranja: {e} !!!")
        return None

def create_map(buses):
    if buses is None:
        buses = []

    kg_coords = [44.0141, 20.9116]
    bus_map = folium.Map(location=kg_coords, zoom_start=13, tiles="CartoDB dark_matter", max_zoom=21)
    
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', name='Satelit', attr='Esri', max_zoom=21).add_to(bus_map)
    folium.TileLayer('OpenStreetMap', name='Standardna mapa').add_to(bus_map)

    active_group = folium.FeatureGroup(name='Aktivni (<10 min)', show=True).add_to(bus_map)
    stale_group = folium.FeatureGroup(name='Stariji signal (10-60 min)', show=True).add_to(bus_map)
    inactive_group = folium.FeatureGroup(name='Neaktivni (>1h)', show=True).add_to(bus_map)
    archive_group = folium.FeatureGroup(name='Arhiva (<2024)', show=False).add_to(bus_map)
    
    marker_cluster = MarkerCluster(disable_clustering_at_zoom=19).add_to(active_group)
    
    search_features = []
    now = datetime.now()
    live_cutoff = now - timedelta(minutes=10)
    stale_cutoff = now - timedelta(hours=1)
    archive_cutoff = datetime(2024, 1, 1)

    for bus in buses:
        try:
            lat = float(bus.get('LATITUDE', '0').replace(',', '.'))
            lon = float(bus.get('LONGITUDE', '0').replace(',', '.'))
            bus_id = bus.get('BUS_ID', 'N/A')
            if lat == 0 and lon == 0: continue
            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S')
            company, vehicle_num = get_vehicle_info(bus_id)
            display_name = f"{company} {vehicle_num}"
            popup_html = f"<b>{bus_id}</b><br><i>{display_name}</i><br><br><b>Linija:</b> {bus.get('ROUTE_CODE', 'N/A')}<br><b>Poslednji signal:</b> {last_seen_dt.strftime('%d.%m.%Y. %H:%M:%S')}"
            
            if last_seen_dt > live_cutoff:
                icon = folium.Icon(color='green', prefix='fa', icon='bus')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(marker_cluster)
            elif last_seen_dt > stale_cutoff:
                icon = folium.Icon(color='orange', prefix='fa', icon='clock-o')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(stale_group)
            elif last_seen_dt >= archive_cutoff:
                icon = folium.Icon(color='lightgray', prefix='fa', icon='info-sign')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(inactive_group)
            else:
                icon = folium.Icon(color='black', prefix='fa', icon='archive')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(archive_group)
            
            if last_seen_dt >= archive_cutoff:
                search_features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]}, 'properties': {'BUS_ID': bus_id}})
        except Exception:
            continue

    search_layer = folium.GeoJson({'type': 'FeatureCollection', 'features': search_features}, marker=folium.CircleMarker(radius=0, opacity=0), name='search_layer').add_to(bus_map)
    Search(layer=search_layer, geom_type='Point', placeholder='Traži garažni broj...', collapsed=True, search_label='BUS_ID', search_zoom=19).add_to(bus_map)
    
    Fullscreen().add_to(bus_map)
    folium.LayerControl().add_to(bus_map)
    
    bus_map.save(MAP_FILE)
    enhance_html_head(MAP_FILE, REFRESH_SECONDS)
    print("Finalna, optimizovana mapa je uspešno generisana.")

def main():
    api_url, headers = get_secrets()
    if not api_url or not headers:
        return
    buses = fetch_bus_data(api_url, headers)
    create_map(buses)

if __name__ == "__main__":
    main()