import requests
import json
import folium
import os
from datetime import datetime, timedelta
from folium.plugins import MarkerCluster, Search, Fullscreen, LocateControl
from jinja2 import Template
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
        print(f"Greška prilikom preuzimanja podataka: {e}")
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

    counts = {'active': 0, 'stale': 0, 'inactive': 0, 'archive': 0}

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
            
            marker_added = False
            if last_seen_dt > live_cutoff:
                icon = folium.Icon(color='green', prefix='fa', icon='bus')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(marker_cluster)
                counts['active'] += 1
                marker_added = True
            elif last_seen_dt > stale_cutoff:
                icon = folium.Icon(color='orange', prefix='fa', icon='clock-o')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(stale_group)
                counts['stale'] += 1
                marker_added = True
            elif last_seen_dt >= archive_cutoff:
                icon = folium.Icon(color='lightgray', prefix='fa', icon='info-sign')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(inactive_group)
                counts['inactive'] += 1
                marker_added = True
            else:
                icon = folium.Icon(color='black', prefix='fa', icon='archive')
                folium.Marker(location=[lat, lon], popup=popup_html, tooltip=display_name, icon=icon).add_to(archive_group)
                counts['archive'] += 1
            
            if marker_added and last_seen_dt >= archive_cutoff:
                search_features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]}, 'properties': {'BUS_ID': bus_id}})
        except Exception:
            continue

    total_vehicles = sum(counts.values())

    stats_template = Template("""
    {% macro html(last_update, active_count, stale_count, inactive_count, archive_count, total_count) %}
        <div id="stats-box">
            <span class="close-btn" onclick="closeStatsBox()">&times;</span>
            <h4>Stanje na mapi</h4>
            <p>Poslednji put ažurirano: <strong>{{ last_update }}</strong></p>
            <ul>
                <li><span class="dot green"></span>Aktivni (&lt;10 min): <strong>{{ active_count }}</strong></li>
                <li><span class="dot orange"></span>Stariji signal (10-60 min): <strong>{{ stale_count }}</strong></li>
                <li><span class="dot gray"></span>Neaktivni (&gt;1h): <strong>{{ inactive_count }}</strong></li>
                <li><span class="dot black"></span>Arhiva (&lt;2024): <strong>{{ archive_count }}</strong></li>
            </ul>
            <p>Ukupno vozila: <strong>{{ total_count }}</strong></p>
        </div>
    {% endmacro %}
    {% macro css() %}
        <style>
            #stats-box {
                position: absolute;
                top: 10px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 9999;
                background-color: rgba(30, 30, 30, 0.85);
                color: #f0f0f0;
                padding: 10px 15px;
                border-radius: 8px;
                font-family: Arial, sans-serif;
                font-size: 14px;
                border: 1px solid #555;
                backdrop-filter: blur(5px);
                -webkit-backdrop-filter: blur(5px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                min-width: 280px;
            }
            #stats-box h4 {
                margin: 0 0 10px 0;
                padding-bottom: 5px;
                border-bottom: 1px solid #666;
                font-size: 16px;
                text-align: center;
            }
            #stats-box p {
                margin: 5px 0;
            }
            #stats-box ul {
                list-style: none;
                padding: 0;
                margin: 10px 0;
            }
            #stats-box li {
                margin-bottom: 5px;
                display: flex;
                align-items: center;
            }
            .close-btn {
                position: absolute;
                top: 2px;
                right: 8px;
                cursor: pointer;
                font-size: 24px;
                color: #aaa;
                font-weight: bold;
                transition: color 0.2s;
            }
            .close-btn:hover {
                color: #fff;
            }
            .dot {
                height: 12px;
                width: 12px;
                border-radius: 50%;
                display: inline-block;
                margin-right: 8px;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .dot.green { background-color: #52D357; }
            .dot.orange { background-color: #F8963E; }
            .dot.gray { background-color: #A0A0A0; }
            .dot.black { background-color: #303030; }
        </style>
    {% endmacro %}
    {% macro js() %}
        <script>
            function closeStatsBox() {
                document.getElementById('stats-box').style.display = 'none';
            }
        </script>
    {% endmacro %}
    """)

    last_update_str = now.strftime('%d.%m.%Y. %H:%M:%S')
    macro = folium.MacroElement()
    macro._template = stats_template
    macro.kwargs = {
        'last_update': last_update_str,
        'active_count': counts['active'],
        'stale_count': counts['stale'],
        'inactive_count': counts['inactive'],
        'archive_count': counts['archive'],
        'total_count': total_vehicles
    }
    bus_map.add_child(macro)

    search_layer = folium.GeoJson({'type': 'FeatureCollection', 'features': search_features}, marker=folium.CircleMarker(radius=0, opacity=0), name='search_layer').add_to(bus_map)
    Search(layer=search_layer, geom_type='Point', placeholder='Traži garažni broj...', collapsed=True, search_label='BUS_ID', search_zoom=19).add_to(bus_map)
    
    Fullscreen().add_to(bus_map)
    folium.LayerControl().add_to(bus_map)
    
    bus_map.save(MAP_FILE)
    enhance_html_head(MAP_FILE, REFRESH_SECONDS)
    print(f"Mapa je uspešno generisana sa {total_vehicles} vozila.")

def main():
    api_url, headers = get_secrets()
    if not api_url or not headers:
        return
    buses = fetch_bus_data(api_url, headers)
    create_map(buses)

if __name__ == "__main__":
    main()