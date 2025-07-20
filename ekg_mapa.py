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

# --- DEBUG PREKIDAČ ---
# Postavi na True da vidiš detaljne poruke o izvršavanju
DEBUG = True

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
    if DEBUG: print("[DEBUG] Učitavam tajne (API URL, token...).")
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
        if DEBUG: print(f"❌ GREŠKA kod dodavanja HTML tagova: {e}")

def fetch_bus_data(api_url, headers):
    if DEBUG: print(f"[DEBUG] Dobavljam podatke sa API-ja: {api_url}")
    try:
        resp = requests.get(api_url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        if DEBUG: print(f"[DEBUG] API odgovor status: {resp.status_code}")
        
        # Proveri da li je odgovor JSON
        try:
            response_json = resp.json()
        except json.JSONDecodeError:
            if DEBUG: print(f"❌ GREŠKA: API nije vratio validan JSON. Sadržaj odgovora:\n{resp.text}")
            return None

        nested = json.loads(response_json['data'])
        buses = nested['ROOT']['BUSES']['BUS']
        if DEBUG: print(f"[DEBUG] Uspešno dobavljeno {len(buses)} vozila sa API-ja.")
        return buses
    except Exception as e:
        if DEBUG:
            print(f"❌ GREŠKA pri dobavljanju podataka sa API-ja: {e}")
            traceback.print_exc()
        return None

def sanitize_for_class(name):
    return re.sub(r'[^a-zA-Z0-9\-_]', '-', name).lower()

def create_map(buses, log_data):
    if DEBUG: print("\n[DEBUG] --- Početak kreiranja mape ---")
    if buses is None:
        if DEBUG: print("[DEBUG] Lista autobusa je 'None', postavljam na praznu listu.")
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
    
    if DEBUG: print(f"[DEBUG] Počinjem obradu {len(buses)} vozila za mapu.")
    for i, bus in enumerate(buses):
        if DEBUG: print(f"\n[DEBUG] Obrada vozila {i+1}/{len(buses)} -> {bus.get('BUS_ID')}")
        try:
            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S').replace(tzinfo=tz)
            lat = float(bus.get('LATITUDE', '0').replace(',', '.'))
            lon = float(bus.get('LONGITUDE', '0').replace(',', '.'))
            if lat == 0 or lon == 0:
                if DEBUG: print("[DEBUG] Preskačem vozilo, koordinate su 0.")
                continue

            bus_id = bus.get('BUS_ID', 'N/A')
            route_code = bus.get('ROUTE_CODE', 'N/A')
            clean_line = get_clean_line_number(route_code)
            operator, internal = get_vehicle_info(bus_id)
            
            if DEBUG: print(f"[DEBUG] Tražim model za Garažni Broj: '{bus_id}'")
            log_entry = log_data.get(bus_id, [None, None, "Nepoznat"])
            if DEBUG: print(f"[DEBUG] Nađen zapis u floti: {log_entry}")
            
            model_name = log_entry[2] if log_entry[2] not in ["Ime Busa", ""] else "Nepoznat"
            model_class = sanitize_for_class(model_name)
            if DEBUG: print(f"[DEBUG] Model: '{model_name}', CSS klasa: '{model_class}'")

            popup_html = (
                f"<b>Linija:</b> {clean_line} ({route_code})<br>"
                f"<b>Vozilo:</b> {bus_id}<br>"
                f"<b>Model:</b> {model_name}<br>"
                f"{operator} #{internal}<br>"
                f"<b>Poslednji signal:</b> {last_seen_dt.strftime('%d.%m.%Y. %H:%M:%S')}"
            )
            tooltip = f"Linija {clean_line} | {operator} #{internal} | {model_name}"
            
            marker = folium.Marker([lat, lon], tooltip=tooltip, popup=popup_html)

            if last_seen_dt >= archive_cutoff:
                if last_seen_dt > ten_min_ago:
                    marker.icon = folium.Icon(color="green", icon="bus", prefix="fa", extra_classes=model_class)
                    fg_active.add_child(marker)
                    counts['active'] += 1
                elif last_seen_dt > sixty_min_ago:
                    marker.icon = folium.Icon(color="darkgreen", icon="bus", prefix="fa", extra_classes=model_class)
                    fg_mid.add_child(marker)
                    counts['mid'] += 1
                elif last_seen_dt > twenty_four_hours_ago:
                    marker.icon = folium.Icon(color="orange", icon="bus", prefix="fa", extra_classes=model_class)
                    fg_24h.add_child(marker)
                    counts['24h'] += 1
                else:
                    marker.icon = folium.Icon(color="lightgray", icon="bus", prefix="fa", extra_classes=model_class)
                    fg_old.add_child(marker)
                    counts['old'] += 1

                search_features.append({'type': 'Feature','geometry': {'type': 'Point', 'coordinates': [lon, lat]},'properties': {'BUS_ID': bus_id}})
            else:
                marker.icon = folium.Icon(color="black", icon="bus", prefix="fa", extra_classes=model_class)
                fg_arch.add_child(marker)
                counts['archive'] += 1

            counts['total'] += 1
            if DEBUG: print(f"[DEBUG] ✔️ Uspešno obrađeno vozilo {bus_id}")
        except Exception as e:
            if DEBUG:
                print(f"❌ GREŠKA pri obradi vozila: {bus}")
                print(f"   Tip greške: {type(e).__name__}, Poruka: {e}")
                traceback.print_exc()
            continue

    if DEBUG: print("[DEBUG] --- Završena obrada vozila za mapu ---")
    if DEBUG: print(f"[DEBUG] Finalni brojači: {counts}")
    
    for fg in [fg_active, fg_mid, fg_24h, fg_old, fg_arch]:
        bus_map.add_child(fg)

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
    if DEBUG: print(f"[DEBUG] Pronađeni jedinstveni modeli za filtere: {unique_models}")

    filter_buttons_html = '<div id="filter-container" style="position: fixed; top: 10px; left: 10px; z-index: 1000; background-color: rgba(255,255,255,0.8); padding: 5px; border-radius: 5px; display: flex; flex-wrap: wrap; gap: 5px;">'
    filter_buttons_html += '<button class="filter-btn active" onclick="filterByModel(\'all\', this)">Svi modeli</button>'
    for model in unique_models:
        model_class = sanitize_for_class(model)
        filter_buttons_html += f'<button class="filter-btn" onclick="filterByModel(\'{model_class}\', this)">{model}</button>'
    filter_buttons_html += '</div>'

    filter_js = """<script>
        function filterByModel(modelClass, btnElement) {
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            btnElement.classList.add('active');
            var markers = document.querySelectorAll('.leaflet-marker-icon');
            markers.forEach(function(marker) {
                var parent = marker.parentElement;
                if (modelClass === 'all') { parent.style.display = ''; }
                else {
                    if (marker.classList.contains(modelClass)) { parent.style.display = ''; }
                    else { parent.style.display = 'none'; }
                }
            });
        }
    </script>"""
    filter_css = """<style>
        .filter-btn { padding: 5px 10px; font-size: 12px; background-color: #fff; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; }
        .filter-btn.active { background-color: #3388ff; color: white; border-color: #3388ff; }
    </style>"""

    bus_map.get_root().html.add_child(folium.Element(filter_buttons_html))
    bus_map.get_root().html.add_child(folium.Element(filter_js))
    bus_map.get_root().html.add_child(folium.Element(filter_css))

    disclaimer_html = """
    <div style="position: fixed; bottom: 10px; right: 10px; z-index: 999; background-color: rgba(30, 30, 30, 0.7); color: #ccc; padding: 5px 10px; border-radius: 5px; font-family: Arial, sans-serif; font-size: 11px; border: 1px solid #555;">
        <p style="margin: 0;"><b>Disclaimer:</b> Ovo je nezvanični, hobi projekat. Podaci su informativnog karaktera i moguće su netačnosti.</p>
    </div>"""
    bus_map.get_root().html.add_child(folium.Element(disclaimer_html))

    bus_map.save(MAP_FILE)
    enhance_html_head(MAP_FILE, REFRESH_SECONDS)
    print(f"✔️ Mapa uspešno generisana ({counts['total']} vozila).")

def load_vehicle_log(log_file=VEHICLE_LOG_FILE):
    if DEBUG: print(f"[DEBUG] Pokušavam da učitam fajl sa flotom: '{log_file}'")
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if DEBUG: print(f"[DEBUG] ✔️ Uspešno učitano {len(data)} zapisa iz '{log_file}'.")
            return data
    except FileNotFoundError:
        if DEBUG: print(f"[DEBUG] ⚠️ Fajl '{log_file}' nije pronađen. Vraćam praznu listu.")
        return {}
    except json.JSONDecodeError:
        if DEBUG: print(f"❌ GREŠKA: Fajl '{log_file}' nije validan JSON. Vraćam praznu listu.")
        return {}
    except Exception as e:
        if DEBUG: print(f"❌ GREŠKA: Nepoznata greška pri čitanju '{log_file}': {e}")
        return {}

def update_and_save_log(buses, log_data, log_file=VEHICLE_LOG_FILE):
    if DEBUG: print("\n[DEBUG] --- Početak ažuriranja i čuvanja 'flota.json' ---")
    if not buses:
        if DEBUG: print("[DEBUG] Nema novih podataka o busevima za ažuriranje evidencije.")
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
                if DEBUG: print(f"[DEBUG] Ažuriram postojeći zapis za {bus_id_str}.")
                log_data[bus_id_str][1] = last_seen_str
            else:
                if DEBUG: print(f"[DEBUG] Dodajem novi zapis za {bus_id_str}.")
                log_data[bus_id_str] = [last_seen_str, last_seen_str, "Ime Busa"]
        except (ValueError, KeyError, TypeError) as e:
            if DEBUG: print(f"❌ GREŠKA pri ažuriranju zapisa za vozilo {bus.get('BUS_ID')}: {e}")
            continue
    
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            sorted_log_data = dict(sorted(log_data.items(), key=lambda item: datetime.strptime(item[1][0], '%d.%m.%Y %H:%M:%S'), reverse=True))
            json.dump(sorted_log_data, f, indent=4, ensure_ascii=False)
        if DEBUG: print(f"[DEBUG] ✔️ Evidencija vozila je uspešno sačuvana u fajl '{log_file}'.")
    except Exception as e:
        if DEBUG: print(f"❌ GREŠKA pri čuvanju JSON fajla: {e}")

    return log_data

def main():
    if DEBUG: print("--- POKRETANJE SKRIPTE ---")
    try:
        log_data = load_vehicle_log()
        api_url, headers = get_secrets()
        buses = fetch_bus_data(api_url, headers)
        
        if buses is not None:
            updated_log_data = update_and_save_log(buses, log_data.copy()) # Šaljemo kopiju da ne utičemo na original
            create_map(buses, updated_log_data)
        else:
            print("Nije moguće generisati mapu i evidenciju jer podaci sa API-ja nisu dobavljeni.")
    except Exception as e:
        if DEBUG:
            print(f"❌ KATASTROFALNA GREŠKA U 'main' FUNKCIJI: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()