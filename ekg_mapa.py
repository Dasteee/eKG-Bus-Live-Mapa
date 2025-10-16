import requests
import json
import folium
import os
import re
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from folium.plugins import MarkerCluster, Search, Fullscreen
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REFRESH_SECONDS = 1800
MAP_FILE = "kragujevac_busevi.html"
VEHICLE_LOG_FILE = "flota.json"

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
        raise ValueError("Nisu postavljene sve environment variables (API_URL, AUTH_TOKEN, DEVICE_ID)")
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
        suburban = code_int % 1000
        if 600 <= suburban <= 613:
            return str(suburban)
        city = code_int % 100
        if 1 <= city <= 30:
            return str(city)
        if 1 <= code_int <= 30 or 600 <= code_int <= 613:
            return str(code_int)
        return route_code
    except (ValueError, TypeError):
        return route_code

def enhance_html_head(html_file, interval_seconds):
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        meta_tags = f"""
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
    <meta http-equiv="refresh" content="{interval_seconds}">
"""
        if '<meta http-equiv="refresh"' not in html_content:
            html_content = html_content.replace('</head>', f'{meta_tags}\n</head>')
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
    except Exception as e:
        print(f"Greška kod dodavanja HTML tagova: {e}")

def fetch_bus_data(api_url, headers):
    try:
        resp = requests.get(api_url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        response_json = resp.json()
        nested = json.loads(response_json['data'])
        buses = nested['ROOT']['BUSES']['BUS']
        return buses
    except Exception as e:
        print(f"Greška pri dobavljanju podataka sa API-ja: {e}")
        traceback.print_exc()
        return None

def sanitize_for_class(name):
    return re.sub(r'[^a-zA-Z0-9\-_]', '-', name).lower()

def create_map(buses, log_data):
    if buses is None:
        buses = []

    tz = ZoneInfo("Europe/Belgrade")
    now = datetime.now(tz)
    ten_min_ago = now - timedelta(minutes=10)
    sixty_min_ago = now - timedelta(minutes=60)
    twenty_four_hours_ago = now - timedelta(hours=24)
    archive_cutoff = datetime(2024, 1, 1, tzinfo=tz)

    kg_coords = [44.0141, 20.9116]
    bus_map = folium.Map(location=kg_coords, zoom_start=13, tiles="CartoDB dark_matter", max_zoom=21)

    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                     name='Satelit', attr='Esri').add_to(bus_map)
    folium.TileLayer('OpenStreetMap', name='Standardna mapa').add_to(bus_map)

    groups = {
        'active': folium.FeatureGroup(name="🟢 Aktivna (0–10 min)", show=True),
        'mid': folium.FeatureGroup(name="🟢 Aktivna (10–60 min)", show=True),
        '24h': folium.FeatureGroup(name="🟠 Neaktivna (1-24h)", show=True),
        'old': folium.FeatureGroup(name="🔴 Neaktivna (>24h)", show=True),
        'archive': folium.FeatureGroup(name="⚫ Arhiva (pre 2024)", show=False)
    }
    
    search_features = []
    counts = {key: 0 for key in groups}
    counts['total'] = 0

    for bus in buses:
        try:
            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S').replace(tzinfo=tz)
            lat = float(bus.get('LATITUDE', '0').replace(',', '.'))
            lon = float(bus.get('LONGITUDE', '0').replace(',', '.'))
            if lat == 0 or lon == 0:
                continue

            bus_id = bus.get('BUS_ID', 'N/A')
            route_code = bus.get('ROUTE_CODE', 'N/A')
            clean_line = get_clean_line_number(route_code)
            operator, internal = get_vehicle_info(bus_id)
            
            log_entry = log_data.get(bus_id, [None, None, "Nepoznat"])
            model_name = log_entry[2] if log_entry[2] not in ["Ime Busa", ""] else ""
            model_class = sanitize_for_class(model_name)

            popup_html = (
                f"<b>Linija:</b> {clean_line} ({route_code})<br>"
                f"<b>Vozilo:</b> {bus_id}<br>"
                f"<b>Model:</b> {model_name}<br>"
                f"{operator} #{internal}<br>"
                f"<b>Poslednji signal:</b> {last_seen_dt.strftime('%d.%m.%Y. %H:%M:%S')}"
            )
            tooltip = f"Linija {clean_line} | {operator} #{internal} | {model_name}"
            
            icon_color = 'lightgray'
            target_group = groups['old']
            group_key = 'old'

            if last_seen_dt >= archive_cutoff:
                if last_seen_dt > ten_min_ago:
                    icon_color, target_group, group_key = 'green', groups['active'], 'active'
                elif last_seen_dt > sixty_min_ago:
                    icon_color, target_group, group_key = 'darkgreen', groups['mid'], 'mid'
                elif last_seen_dt > twenty_four_hours_ago:
                    icon_color, target_group, group_key = 'orange', groups['24h'], '24h'
                search_features.append({'type': 'Feature','geometry': {'type': 'Point', 'coordinates': [lon, lat]},'properties': {'BUS_ID': bus_id}})
            else:
                icon_color, target_group, group_key = 'black', groups['archive'], 'archive'

            icon = folium.Icon(color=icon_color, icon="bus", prefix="fa")
            icon.options['extraClasses'] = model_class
            
            marker = folium.Marker([lat, lon], tooltip=tooltip, popup=popup_html, icon=icon)
            target_group.add_child(marker)
            
            counts[group_key] += 1
            counts['total'] += 1

        except Exception as e:
            print(f"❌ GREŠKA pri obradi vozila: {bus.get('BUS_ID')}. Poruka: {e}")
            traceback.print_exc()
            continue

    for group in groups.values():
        bus_map.add_child(group)

    if search_features:
        search_layer = folium.GeoJson({'type': 'FeatureCollection', 'features': search_features}, name="Pretraga", marker=folium.CircleMarker(radius=0, fill_opacity=0, opacity=0))
        bus_map.add_child(search_layer)
        Search(layer=search_layer, geom_type='Point', placeholder='Traži garažni broj...', collapsed=True, search_label='BUS_ID', search_zoom=18).add_to(bus_map)

    Fullscreen().add_to(bus_map)
    folium.LayerControl(collapsed=False).add_to(bus_map)

    stats_html = f"""
    <div id="stats-box" style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%); background-color: rgba(0,0,0,0.75); color: white; padding: 10px 15px; border-radius: 8px; z-index: 1000; font-size: 14px; min-width: 280px;">
        <span style="position: absolute; top: 5px; right: 10px; cursor: pointer; color: #fff; font-weight: bold; font-size: 18px;" onclick="document.getElementById('stats-box').style.display='none';">&times;</span>
        <b>Stanje na mapi</b><br> Ažurirano: {datetime.now(ZoneInfo("Europe/Belgrade")).strftime('%d.%m.%Y. %H:%M:%S')}<br>
        Aktivna: {counts['active']}<br> 10-60 min: {counts['mid']}<br> 1-24h: {counts['24h']}<br> 24h+: {counts['old']}<br> Arhiva: {counts['archive']}
    </div>"""
    bus_map.get_root().html.add_child(folium.Element(stats_html))

    unique_models = sorted(list(set(v[2] for v in log_data.values() if v[2] not in ["Ime Busa", "Nepoznat", ""])))

    filter_control_html = """
    <div id="filter-control-container">
        <button id="funnel-btn" onclick="toggleFilterMenu()">
            <i class="fa fa-filter" style="font-size: 14px;"></i>
        </button>
        <div id="filter-menu" class="hidden">
            <button class="filter-btn active" onclick="filterByModel('all', this)">Svi modeli</button>
    """
    for model in unique_models:
        model_class = sanitize_for_class(model)
        filter_control_html += f'<button class="filter-btn" onclick="filterByModel(\'{model_class}\', this)">{model}</button>'
    filter_control_html += """
        </div>
    </div>
    """

    filter_js = """
    <script>
        function toggleFilterMenu() {
            document.getElementById('filter-menu').classList.toggle('hidden');
        }

        function filterByModel(modelClass, btnElement) {
            document.getElementById('filter-menu').classList.add('hidden');
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            btnElement.classList.add('active');
            
            var markerIcons = document.querySelectorAll('.leaflet-marker-icon');
            markerIcons.forEach(function(markerIcon) {
                var markerContainer = markerIcon.parentElement;
                if (modelClass === 'all') {
                    markerContainer.style.display = '';
                } else {
                    var iTag = markerIcon.querySelector('i');
                    if (iTag && iTag.classList.contains(modelClass)) {
                        markerContainer.style.display = '';
                    } else {
                        markerContainer.style.display = 'none';
                    }
                }
            });
        }
    </script>
    """

    filter_css = """
    <style>
        #filter-control-container {
            position: fixed;
            top: 10px;
            left: 10px;
            z-index: 1000;
        }
        #funnel-btn {
            background-color: #fff;
            border: 2px solid rgba(0,0,0,0.2);
            border-radius: 4px;
            width: 34px;
            height: 34px;
            cursor: pointer;
            line-height: 30px;
            text-align: center;
        }
        #funnel-btn:hover {
            background-color: #f4f4f4;
        }
        #filter-menu {
            position: absolute;
            top: 40px;
            left: 0;
            background-color: white;
            border-radius: 5px;
            padding: 5px;
            display: flex;
            flex-direction: column;
            gap: 3px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.65);
            max-height: 300px;
            overflow-y: auto;
        }
        #filter-menu.hidden {
            display: none;
        }
        .filter-btn {
            padding: 8px 12px;
            font-size: 14px;
            background-color: #fff;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            text-align: left;
            width: 100%;
        }
        .filter-btn:hover {
            background-color: #f0f0f0;
        }
        .filter-btn.active {
            background-color: #3388ff;
            color: white;
        }
    </style>
    """

    bus_map.get_root().html.add_child(folium.Element(filter_control_html))
    bus_map.get_root().html.add_child(folium.Element(filter_js))
    bus_map.get_root().html.add_child(folium.Element(filter_css))

    bus_map.save(MAP_FILE)
    enhance_html_head(MAP_FILE, REFRESH_SECONDS)
    print(f"✔️ Mapa uspešno generisana ({counts['total']} vozila).")

def load_vehicle_log(log_file=VEHICLE_LOG_FILE):
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def update_and_save_log(buses, log_data, log_file=VEHICLE_LOG_FILE):
    if not buses:
        return log_data

    tz = ZoneInfo("Europe/Belgrade")
    archive_cutoff = datetime(2024, 1, 1, tzinfo=tz)

    for bus in buses:
        try:
            bus_id_str = bus.get('BUS_ID')
            if not bus_id_str:
                continue

            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S').replace(tzinfo=tz)
            if last_seen_dt < archive_cutoff:
                continue

            last_seen_str = last_seen_dt.strftime('%d.%m.%Y %H:%M:%S')

            if bus_id_str in log_data:
                log_data[bus_id_str][1] = last_seen_str
            else:
                log_data[bus_id_str] = [last_seen_str, last_seen_str, "Ime Busa"]
        except (ValueError, KeyError, TypeError):
            continue
    
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            sorted_log_data = dict(sorted(log_data.items(), key=lambda item: datetime.strptime(item[1][0], '%d.%m.%Y %H:%M:%S'), reverse=True))
            json.dump(sorted_log_data, f, indent=4, ensure_ascii=False)
        print(f"✔️ Evidencija vozila je uspešno ažurirana u fajlu '{log_file}'.")
    except Exception as e:
        print(f"Greška pri čuvanju JSON fajla: {e}")

    return log_data

def main():
    try:
        log_data = load_vehicle_log()
        api_url, headers = get_secrets()
        buses = fetch_bus_data(api_url, headers)
        
        if buses is not None:
            updated_log_data = update_and_save_log(buses, log_data.copy())
            create_map(buses, updated_log_data)
        else:
            print("Nije moguće generisati mapu i evidenciju jer podaci sa API-ja nisu dobavljeni.")
    except Exception as e:
        print(f"❌ KATASTROFALNA GREŠKA U 'main' FUNKCIJI: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
