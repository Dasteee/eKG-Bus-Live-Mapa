import requests
import json
import folium
import os
from datetime import datetime, timedelta
from folium.plugins import Search, Fullscreen, LocateControl
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REFRESH_SECONDS = 60
MAP_FILE = "kragujevac_busevi.html"

def get_secrets():
    print("\n---> Korak 1: Provera 'tajni' (secrets)...")
    api_url = os.getenv("API_URL")
    auth_token = os.getenv("AUTH_TOKEN")
    device_id = os.getenv("DEVICE_ID")

    print(f"Tip podatka za API_URL: {type(api_url)}")
    print(f"Tip podatka za AUTH_TOKEN: {type(auth_token)}")
    print(f"Tip podatka za DEVICE_ID: {type(device_id)}")

    print(f"Da li API_URL ima sadržaj? {bool(api_url)}")
    print(f"Da li AUTH_TOKEN ima sadržaj? {bool(auth_token)}")
    print(f"Da li DEVICE_ID ima sadržaj? {bool(device_id)}")

    if auth_token:
        print(f"Početak tokena (prvih 5 karaktera): {auth_token[:5]}")
    
    if not all([api_url, auth_token, device_id]):
        print("\n!!! KRITIČNA GREŠKA: Jedna ili više 'tajni' nisu ispravno učitane. Proveri imena i vrednosti u GitHub Secrets. Prekidam izvršavanje. !!!")
        return None, None

    print("\n--- 'Tajne' su uspešno učitane. ---")
    
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

def add_auto_refresh(html_file, interval_seconds):
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        meta_tag = f'<meta http-equiv="refresh" content="{interval_seconds}">'
        if meta_tag not in html_content:
            html_content = html_content.replace('</head>', f'{meta_tag}\n</head>')
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
    except Exception as e:
        print(f"Greška kod dodavanja auto-refresha: {e}")

def fetch_bus_data(api_url, headers):
    print(f"\n---> Korak 2: Preuzimanje podataka sa API-ja...")
    print(f"Šaljem zahtev na URL: {api_url}")
    try:
        response = requests.get(api_url, headers=headers, timeout=15, verify=False)
        print(f"Server je odgovorio sa status kodom: {response.status_code}")
        response.raise_for_status()
        nested_data = json.loads(response.json()['data'])
        buses = nested_data['ROOT']['BUSES']['BUS']
        print(f"Podaci uspešno parsirani. Pronađeno {len(buses)} unosa za autobuse.")
        return buses
    except Exception as e:
        print(f"!!! GREŠKA prilikom preuzimanja ili parsiranja: {e} !!!")
        return None

def create_map(buses):
    print("\n---> Korak 3: Kreiranje mape sa svim autobusima (jednostavna verzija)...")
    if buses is None:
        buses = []
    
    print(f"Funkcija create_map je primila {len(buses)} autobusa za iscrtavanje.")

    kg_coords = [44.0141, 20.9116]
    bus_map = folium.Map(location=kg_coords, zoom_start=13, tiles="CartoDB dark_matter")
    
    live_cutoff = datetime.now() - timedelta(minutes=10)
    buses_drawn = 0

    for bus in buses:
        try:
            lat = float(bus.get('LATITUDE', '0').replace(',', '.'))
            lon = float(bus.get('LONGITUDE', '0').replace(',', '.'))
            bus_id = bus.get('BUS_ID', 'N/A')
            if lat == 0 and lon == 0:
                continue

            last_seen_dt = datetime.strptime(bus.get('LAST_GPS_TIME'), '%Y%m%d%H%M%S')
            is_live = last_seen_dt > live_cutoff

            icon_color = 'green' if is_live else 'gray'
            
            popup_html = f"<b>Vozilo: {bus_id}</b><br>Linija: {bus.get('ROUTE_CODE', 'N/A')}<br>Poslednji signal: {last_seen_dt.strftime('%d.%m.%Y. %H:%M:%S')}"

            folium.Marker(
                location=[lat, lon],
                popup=popup_html,
                tooltip=f"Vozilo: {bus_id}",
                icon=folium.Icon(color=icon_color)
            ).add_to(bus_map)
            
            buses_drawn += 1

        except Exception as e:
            print(f"!!! Greška pri obradi busa {bus.get('BUS_ID')}: {e} !!!")
            continue
    
    print(f"Iscrtano je {buses_drawn} od {len(buses)} autobusa na mapi.")
    
    bus_map.save(MAP_FILE)
    add_auto_refresh(MAP_FILE, REFRESH_SECONDS)
    print(f"\n--- Mapa sa svim autobusima (jednostavna) je generisana. ---")

def main():
    api_url, headers = get_secrets()
    if not api_url or not headers:
        return 
    buses = fetch_bus_data(api_url, headers)
    create_map(buses)

if __name__ == "__main__":
    main()