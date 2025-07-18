## Opis Projekta
[🇬🇧 English version available below](#english)

Ova interaktivna mapa predstavlja naprednu alternativu zvaničnoj aplikaciji za praćenje javnog prevoza. Za razliku od zvanične aplikacije, koja često ograničava prikaz na jednu liniju i skriva ključne podatke poput garažnog broja, ovaj alat vam daje potpunu kontrolu i transparentnost.

Cilj je pružiti sveobuhvatan pregled saobraćaja, obogaćen funkcionalnostima koje ne postoje u zvaničnoj verziji. Pored osnovnog prikaza svih vozila i njihovih garažnih brojeva, mapa nudi i:

* **Status vozila:** Jasan prikaz razlike između aktivnih (trenutno u pokretu) i **neaktivnih vozila** (koja duže vreme nisu poslala signal).
* **Pretragu:** Brza **pretraga** po garažnom broju za lako pronalaženje bilo kog vozila na mapi.
* **Statistiku:** **Statistika** u realnom vremenu koja prikazuje ukupan broj vozila na mapi i broj trenutno aktivnih.
* **Arhivu:** Mogućnost pregleda podataka o starijim vozilima koja više nisu u opticaju, korisno za analizu voznog parka.
* **(Uskoro) Modeli autobusa:** U pripremi je i prikaz tačnog **modela autobusa** za svako vozilo.

### Kako pogledati mapu

Postoje dva načina da pristupite mapi, u zavisnosti od vaših potreba.

#### Način 1: Preko linka (Preporučeno)

Najjednostavniji način je da posetite već hostovanu, živu verziju mape koja se automatski ažurira.

**[➡️ Otvorite mapu uživo ⬅️](https://dasteee.github.io/eKG-Bus-Live-Mapa/kragujevac_busevi.html)**

---
#### Način 2: Lokalno pokretanje (Za napredne korisnike)

Ovaj način je namenjen programerima koji žele da pokreću, analiziraju ili modifikuju kod na svom računaru.

<details>
  <summary><strong>Kliknite ovde za uputstvo za lokalno pokretanje</strong></summary>
  
  1. **Preduslovi:** Potrebno je da imate instaliran Python 3 na svom sistemu.
  
  2. **Preuzmite kod:** Klonirajte ovaj repozitorijum na svoj računar komandom:
     ```bash
     git clone https://github.com/Dasteee/eKG-Bus-Live-Mapa.git
     cd eKG-Bus-Live-Mapa
     ```
  
  3. **Instalirajte zavisnosti:**
     ```bash
     pip install -r requirements.txt
     ```

  4. **Pronađite tokene:** Da bi skripta radila, morate sami da pronađete lične kredencijale (`API_URL`, `AUTH_TOKEN`, `DEVICE_ID`). To se radi analizom mrežnog saobraćaja (eng. *network sniffing*) zvanične mobilne aplikacije. Ovo je najkompleksniji korak i zahteva tehničko znanje.
  
  5. **Postavite tokene:** Pronađene vrednosti postavite kao *environment variables* (promenljive okruženja) na vašem sistemu. Nemojte ih upisivati direktno u kod.
  
  6. **Pokrenite skriptu:** Izvršite glavnu Python skriptu.
      ```bash
      python tvoja_skripta.py
      ```
  Nakon ovoga, `html` fajl sa mapom će biti generisan u direktorijumu projekta i možete ga otvoriti u bilo kom veb pregledaču.
</details>

<details>
  <summary><strong>Važno Pravno Obaveštenje i Odricanje od Odgovornosti</strong></summary>
  
  #### 1. Odsustvo povezanosti
  Ovaj projekat je nezavisan i nekomercijalan. **Izričito se navodi da projekat nije ni na koji način zvanično povezan, odobren, niti sponzorisan od strane JKP 'Šumadija' Kragujevac, Gradske agencije za saobraćaj, sistema BusPlus, prevoznika 'Vulović transport d.o.o.' i 'Strela-Obrenovac', niti bilo koje druge povezane pravne ili fizičke osobe.** Projekat je razvijen samostalno, bez ikakve saradnje ili komunikacije sa navedenim entitetima.

  #### 2. Korišćenje podataka i svrha projekta
  Aplikacija pristupa podacima preko tehničkog interfejsa (API) koji je javno dostupan, ali se ovde koristi u svrhe koje verovatno nisu predviđene od strane originalnog provajdera. Svrha ovog projekta je isključivo edukativna, informativna i predstavlja tehničku demonstraciju (alternativni klijent) za pregled informacija koje su javno dostupne. **Ne postoji namera da se konkuriše zvaničnim servisima niti da se ostvari bilo kakva materijalna korist.**

  #### 3. Intelektualna svojina
  Svi žigovi, uslužni znaci, nazivi kompanija (uključujući, ali ne ograničavajući se na "JKP Šumadija", "BusPlus", "Vulović", "Strela") i logotipi pomenuti u ovom projektu su vlasništvo njihovih odgovarajućih vlasnika. Njihovo korišćenje je minimalno i služi isključivo u svrhu identifikacije i opisnog izveštavanja (nominativna upotreba), i ne podrazumeva nikakvu povezanost sa vlasnicima žigova niti sponzorstvo.

  #### 4. Garancija i odgovornost
  Softver i podaci se pružaju **"takvi kakvi jesu"**, bez ikakvih garancija, izričitih ili podrazumevanih. Autor se odriče svake odgovornosti za bilo kakvu štetu ili gubitke koji mogu nastati korišćenjem ove aplikacije. Korisnik preuzima sav rizik vezan za tačnost, kompletnost i upotrebljivost podataka.
</details>

## English
#### Project Description

This interactive map serves as an advanced alternative to the official Kragujevac public transport tracking application. Unlike the official app, which often restricts the view to a single stop and hides key data like the vehicle's garage number, this tool gives you complete control and transparency.

The goal is to provide a comprehensive overview of the traffic, enriched with functionalities that do not exist in the official version. In addition to the basic display of all vehicles and their garage numbers, the map also offers:

* **Vehicle Status:** A clear distinction between active (currently moving) and **inactive vehicles** (those that haven't sent a signal for a while).
* **Search:** A fast **search** by garage number to easily locate any vehicle on the map.
* **Statistics:** Real-time **statistics** showing the total number of vehicles on the map and the number of currently active ones.
* **Archive:** The ability to view data on older vehicles that are no longer in circulation, useful for fleet analysis.
* **(Coming Soon) Bus Models:** A feature to display the exact **bus model** for each vehicle.

### How to Access the Map

There are two ways to access the map, depending on your needs.

#### Method 1: Via Link (Recommended)

The easiest way is to visit the already hosted, live version of the map, which updates automatically.

**[➡️ Open the Live Map ⬅️](https://dasteee.github.io/eKG-Bus-Live-Mapa/kragujevac_busevi.html)**

---
#### Method 2: Running Locally (For Advanced Users)

This method is intended for developers who want to run, analyze, or modify the code on their own computer.

<details>
  <summary><strong>Click here for instructions on running locally</strong></summary>
  
  1. **Prerequisites:** You need to have Python 3 installed on your system.
  
  2. **Download the code:** Clone this repository to your computer with the command:
     ```bash
     git clone https://github.com/Dasteee/eKG-Bus-Live-Mapa.git
     cd eKG-Bus-Live-Mapa
     ```
  
  3. **Install dependencies:**
     ```bash
     pip install -r requirements.txt
     ```

  4. **Find your tokens:** For the script to work, you must find your personal credentials (`API_URL`, `AUTH_TOKEN`, `DEVICE_ID`). This is done by analyzing the network traffic (sniffing) of the official mobile application. This is the most complex step and requires technical knowledge.
  
  5. **Set the tokens:** Set the values you found as environment variables on your system. Do not hardcode them into the script.
  
  6. **Run the script:** Execute the main Python script.
      ```bash
      python your_script.py
      ```
  After this, the `html` file with the map will be generated in the project's directory, and you can open it in any web browser.
</details>
<details>
  <summary><strong>Important Legal Notice and Disclaimer (Click for details)</strong></summary>
  
  #### 1. No Affiliation
  This project is independent and non-commercial. **It is explicitly stated that the project is in no way officially affiliated with, endorsed, or sponsored by JKP 'Šumadija' Kragujevac, the City Transport Agency, the BusPlus system, operators 'Vulović transport d.o.o.' and 'Strela-Obrenovac', or any other related legal or natural person.** This project was developed independently, without any cooperation or communication with the aforementioned entities.

  #### 2. Data Usage and Project Purpose
  The application accesses data through a technical interface (API) that is publicly available but is used here for purposes likely not intended by the original provider. The purpose of this project is strictly educational, informational, and serves as a technical demonstration (an alternative client) for viewing publicly available information. **There is no intention to compete with official services or to generate any material profit.**

  #### 3. Intellectual Property
  All trademarks, service marks, company names (including, but not limited to, "JKP Šumadija," "BusPlus," "Vulović," "Strela"), and logos mentioned in this project are the property of their respective owners. Their use is minimal and serves exclusively for identification and descriptive reporting purposes (nominative use), and does not imply any association with or endorsement by the trademark holders.

  #### 4. Warranty and Liability
  The software and data are provided **"as is"**, without warranty of any kind, express or implied. The author disclaims all liability for any damages or losses that may arise from the use of this application. The user assumes all risk related to the accuracy, completeness, and usability of the data.
</details>