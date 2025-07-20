import requests
import json
import folium
import os
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
        nested = json.loads(resp.json()['data'])
        return nested['ROOT']['BUSES']['BUS']
    except Exception as e:
        print(f"Greška pri fetch-u podataka: {e}")
        return None

def create_map(buses):
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

    fg_active = folium.FeatureGroup(name="🟢 Aktivna (0–10 min)", show=True)
    fg_mid = folium.FeatureGroup(name="🟢 Aktivna (10–60 min)", show=True)
    fg_24h = folium.FeatureGroup(name="🟠 Neaktivna (1-24h)", show=True)
    fg_old = folium.FeatureGroup(name="🔴 Neaktivna (>24h)", show=False)
    fg_arch = folium.FeatureGroup(name="⚫ Arhiva (pre 2024)", show=False)

    search_features = []
    counts = {'active': 0, 'mid': 0, '24h': 0, 'old': 0, 'archive': 0, 'total': 0}

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

            popup = (
                f"<b>Linija:</b> {clean_line} ({route_code})<br>"
                f"<b>Vozilo:</b> {bus_id}<br>"
                f"{operator} #{internal}<br>"
                f"<b>Poslednji signal:</b> {last_seen_dt.strftime('%d.%m.%Y. %H:%M:%S')}"
            )
            tooltip = f"Linija {clean_line} | {operator} #{internal}"
            icon = folium.Icon(color="gray", icon="bus", prefix="fa")

            if last_seen_dt >= archive_cutoff:
                if last_seen_dt > ten_min_ago:
                    icon = folium.Icon(color="green", icon="bus", prefix="fa")
                    fg_active.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup, icon=icon))
                    counts['active'] += 1
                elif last_seen_dt > sixty_min_ago:
                    icon = folium.Icon(color="darkgreen", icon="bus", prefix="fa")
                    fg_mid.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup, icon=icon))
                    counts['mid'] += 1
                elif last_seen_dt > twenty_four_hours_ago:
                    icon = folium.Icon(color="orange", icon="bus", prefix="fa")
                    fg_24h.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup, icon=icon))
                    counts['24h'] += 1
                else:
                    icon = folium.Icon(color="lightgray", icon="bus", prefix="fa")
                    fg_old.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup, icon=icon))
                    counts['old'] += 1

                search_features.append({
                    'type': 'Feature',
                    'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                    'properties': {'BUS_ID': bus_id}
                })
            else:
                icon = folium.Icon(color="black", icon="bus", prefix="fa")
                fg_arch.add_child(folium.Marker([lat, lon], tooltip=tooltip, popup=popup, icon=icon))
                counts['archive'] += 1

            counts['total'] += 1
        except Exception:
            continue

    for fg in [fg_active, fg_mid, fg_24h, fg_old, fg_arch]:
        bus_map.add_child(fg)

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

    Fullscreen().add_to(bus_map)
    folium.LayerControl(collapsed=False).add_to(bus_map)

    stats_html = f"""
    <div id="stats-box" style="position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
                background-color: rgba(0,0,0,0.75); color: white; padding: 10px 15px;
                border-radius: 8px; z-index: 999; font-size: 14px; min-width: 280px;">
        <span style="position: absolute; top: 5px; right: 10px; cursor: pointer; color: #fff; font-weight: bold; font-size: 18px;"
            onclick="document.getElementById('stats-box').style.display='none';">&times;</span>
        <b>Stanje na mapi</b><br>
        Ažurirano: {datetime.now(ZoneInfo("Europe/Belgrade")).strftime('%d.%m.%Y. %H:%M:%S')}<br>
        Aktivna: {counts['active']}<br>
        10-60 min: {counts['mid']}<br>
        1-24h: {counts['24h']}<br>
        24h+: {counts['old']}<br>
        Arhiva: {counts['archive']}
    </div>
    """
    bus_map.get_root().html.add_child(folium.Element(stats_html))

    disclaimer_html = """
    <div style="position: absolute; bottom: 10px; right: 10px; z-index: 999; background-color: rgba(30, 30, 30, 0.7); color: #ccc; padding: 5px 10px; border-radius: 5px; font-family: Arial, sans-serif; font-size: 11px; border: 1px solid #555;">
        <p style="margin: 0;"><b>Disclaimer:</b> Ovo je nezvanični, hobi projekat. Podaci su informativnog karaktera i moguće su netačnosti.</p>
    </div>
    """
    bus_map.get_root().html.add_child(folium.Element(disclaimer_html))

    bus_map.save(MAP_FILE)
    enhance_html_head(MAP_FILE, REFRESH_SECONDS)
    print(f"✔️ Mapa uspešno generisana ({counts['total']} vozila).")

def update_vehicle_log(buses, log_file=VEHICLE_LOG_FILE):
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log_data = {}

    tz = ZoneInfo("Europe/Belgrade")
    archive_cutoff = datetime(2024, 1, 1, tzinfo=tz)

    if not buses:
        print("Nema podataka o busevima za ažuriranje evidencije.")
        return

    for bus in buses:
        try:
            bus_id_str = bus.get('BUS_ID')
            if not bus_id_str:
                continue

            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S').replace(tzinfo=tz)
            last_seen_str = last_seen_dt.strftime('%d.%m.%Y %H:%M:%S')

            if last_seen_dt < archive_cutoff:
                continue

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

def main():
    try:
        api_url, headers = get_secrets()
        buses = fetch_bus_data(api_url, headers)
        if buses:
            create_map(buses)
            update_vehicle_log(buses)
        else:
            print("Nije moguće generisati mapu i evidenciju bez podataka o vozilima.")
    except Exception as e:
        print(f"Došlo je do greške u izvršavanju programa: {e}")

if __name__ == "__main__":
    main()