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
    print("\n---> Korak 3: Kreiranje TEST mape...")
    print(f"Ima {len(buses) if buses else 0} autobusa, ali ću ih ignorisati i crtam samo jedan test marker.")

    kg_coords = [44.0141, 20.9116]
    
    bus_map = folium.Map(location=kg_coords, zoom_start=13, tiles="OpenStreetMap")

    try:
        folium.Marker(
            location=kg_coords,
            popup="TEST MARKER - AKO VIDIŠ OVO, OSNOVA RADI!",
            tooltip="TEST",
            icon=folium.Icon(color='red', prefix='fa', icon='star')
        ).add_to(bus_map)
        print("Test marker je uspešno DODAT na map objekat.")
    except Exception as e:
        print(f"!!! GREŠKA prilikom dodavanja test markera: {e} !!!")

    bus_map.save(MAP_FILE)
    add_auto_refresh(MAP_FILE, REFRESH_SECONDS)
    print(f"\n--- Test mapa je generisana. ---")

def main():
    api_url, headers = get_secrets()
    if not api_url or not headers:
        return 
    buses = fetch_bus_data(api_url, headers)
    create_map(buses)

if __name__ == "__main__":
    main()