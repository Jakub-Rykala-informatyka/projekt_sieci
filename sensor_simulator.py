import time
import json
import random
from datetime import datetime
import paho.mqtt.client as mqtt


ADRES_BROKERA = "127.0.0.1"   # broker 
PORT_MQTT = 1883
BAZA_TEMATU = "iot/czujnik"   # baza topiców
ID_URZADZENIA = "czujniki-01"
OKRES_S = 2                   # okres wysylania

# Stan poczatkowy
stan = {
    "temperatura_C": 22.0,
    "wilgotnosc_proc": 45.0,
    "swiatlo_lux": 300.0,
    "wiatr_kierunek_deg": 90.0,
    "wiatr_predkosc_ms": 3.0,
}

def ogranicz(x, min_val, max_val):
    return max(min_val, min(x, max_val))

def aktualizuj_stan():
    # Temperatura
    stan["temperatura_C"] = ogranicz(stan["temperatura_C"] + random.uniform(-0.15, 0.15), -10.0, 40.0)

    # Wilgotnosc
    stan["wilgotnosc_proc"] = ogranicz(stan["wilgotnosc_proc"] + random.uniform(-0.6, 0.6), 10.0, 95.0)

    # swiatlo
    chmura = random.choice([0, 0, 0, -120, -80, 50])  
    stan["swiatlo_lux"] = ogranicz(stan["swiatlo_lux"] + random.uniform(-30, 30) + chmura, 0.0, 2000.0)

    # Kierunek wiatru
    stan["wiatr_kierunek_deg"] = (stan["wiatr_kierunek_deg"] + random.uniform(-8, 8)) % 360.0

    # Predkosc wiatru
    podmuch = random.choice([0, 0, 0, 0, 1.5, 2.5, -1.0])
    stan["wiatr_predkosc_ms"] = ogranicz(stan["wiatr_predkosc_ms"] + random.uniform(-0.3, 0.3) + podmuch, 0.0, 25.0)

def opublikuj(client, nazwa_czujnika, wartosc, jednostka):
    # payload w JSON 
    dane = {
        "id": ID_URZADZENIA,
        "czas": datetime.now().isoformat(timespec="seconds"),
        "wartosc": wartosc,
        "jednostka": jednostka
    }
    temat = f"{BAZA_TEMATU}/{nazwa_czujnika}"
    client.publish(temat, json.dumps(dane), qos=0, retain=False)

def main():
    client = mqtt.Client(client_id=f"{ID_URZADZENIA}-{random.randint(1000,9999)}")
    client.connect(ADRES_BROKERA, PORT_MQTT, 60)

    print(f"Start symulatora 5 czujników- broker MQTT: {ADRES_BROKERA}:{PORT_MQTT}")
    print(f"Tematy: {BAZA_TEMATU}/temperatura, wilgotnosc, swiatlo, wiatr_kierunek, wiatr_predkosc")
    print(f"Interwal wysylania: {OKRES_S}s\n")

    while True:
        aktualizuj_stan()

        opublikuj(client, "temperatura", round(stan["temperatura_C"], 2), "°C")
        opublikuj(client, "wilgotnosc", round(stan["wilgotnosc_proc"], 1), "%")
        opublikuj(client, "swiatlo", int(stan["swiatlo_lux"]), "lux")
        opublikuj(client, "wiatr_kierunek", int(stan["wiatr_kierunek_deg"]), "deg")
        opublikuj(client, "wiatr_predkosc", round(stan["wiatr_predkosc_ms"], 2), "m/s")

        print(
            "Wyslano:",
            f"T={stan['temperatura_C']:.2f}°C,",
            f"H={stan['wilgotnosc_proc']:.1f}%,",
            f"L={stan['swiatlo_lux']:.0f} lux,",
            f"Kier={stan['wiatr_kierunek_deg']:.0f}°,",
            f"Wiatr={stan['wiatr_predkosc_ms']:.2f} m/s"
        )

        time.sleep(OKRES_S)

if __name__ == "__main__":
    main()
