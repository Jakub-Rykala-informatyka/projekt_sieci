import json
import os
import threading
from datetime import datetime

from flask import Flask, jsonify, Response, request
import paho.mqtt.client as mqtt
from tinydb import TinyDB, Query

# MQTT 
BROKER = "127.0.0.1"
PORT = 1883
TOPIC = "iot/czujnik/#"

# Tinydb
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "iot_db.json")
db = TinyDB(DB_PATH)

MAX_POINTS_PER_SENSOR = 600

latest = {
    "temperatura": None,
    "wilgotnosc": None,
    "swiatlo": None,
    "wiatr_kierunek": None,
    "wiatr_predkosc": None,
}

def trim_sensor_history(sensor_name: str):
    Sensor = Query()
    rows = db.search(Sensor.sensor == sensor_name)
    if len(rows) <= MAX_POINTS_PER_SENSOR:
        return
    rows_sorted = sorted(rows, key=lambda r: r.get("ts", ""))
    to_delete = rows_sorted[: max(0, len(rows_sorted) - MAX_POINTS_PER_SENSOR)]
    for r in to_delete:
        db.remove(doc_ids=[r.doc_id])

def on_message(client, userdata, msg):
    key = msg.topic.split("/")[-1]
    try:
        payload = json.loads(msg.payload.decode("utf-8", errors="replace"))
    except Exception:
        payload = {"raw": msg.payload.decode("utf-8", errors="replace")}

    if key in latest:
        latest[key] = payload

    record = {
        "sensor": key,
        "topic": msg.topic,
        "device_id": payload.get("id"),
        "ts": payload.get("czas") or datetime.now().isoformat(timespec="seconds"),
        "value": payload.get("wartosc"),
        "unit": payload.get("jednostka"),
        "raw": payload,
    }
    db.insert(record)

    if key in latest:
        trim_sensor_history(key)

def mqtt_loop():
    c = mqtt.Client(client_id="iot-server")
    c.on_message = on_message
    c.connect(BROKER, PORT, 60)
    c.subscribe(TOPIC)
    c.loop_forever()

app = Flask(__name__)

@app.get("/api/latest")
def api_latest():
    return jsonify(latest)

@app.get("/api/history/<sensor>")
def api_history(sensor):
    n = int(request.args.get("n", 120))
    Sensor = Query()
    rows = db.search(Sensor.sensor == sensor)
    rows = sorted(rows, key=lambda r: r.get("ts", ""))
    rows = rows[-n:]
    labels = [r.get("ts") for r in rows]
    values = [r.get("value") for r in rows]
    unit = rows[-1].get("unit") if rows else ""
    return jsonify({"sensor": sensor, "labels": labels, "values": values, "unit": unit})

@app.get("/")
def index():
    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>IoT Dashboard</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 16px; }
    .title { font-size: 14px; color: #666; margin-bottom: 6px; }
    .value { font-size: 28px; font-weight: 700; }
    .meta { margin-top: 8px; font-size: 12px; color: #666; }

    .charts { margin-top: 24px; display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }
    .chart-card { border: 1px solid #ddd; border-radius: 12px; padding: 16px; }
    canvas { width: 100% !important; height: 260px !important; }
  </style>
</head>
<body>
  <h2>IoT Dashboard</h2>
  <div class="grid" id="grid"></div>

  <h3>Wykresy</h3>
  <div class="charts">
    <div class="chart-card"><div class="title">Temperatura</div><canvas id="ch_temperatura"></canvas></div>
    <div class="chart-card"><div class="title">Wilgotność</div><canvas id="ch_wilgotnosc"></canvas></div>
    <div class="chart-card"><div class="title">Światło</div><canvas id="ch_swiatlo"></canvas></div>
    <div class="chart-card"><div class="title">Kierunek wiatru</div><canvas id="ch_wiatr_kierunek"></canvas></div>
    <div class="chart-card"><div class="title">Prędkość wiatru</div><canvas id="ch_wiatr_predkosc"></canvas></div>
  </div>

<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
const sensors = [
  ["temperatura", "Temperatura"],
  ["wilgotnosc", "Wilgotność"],
  ["swiatlo", "Światło"],
  ["wiatr_kierunek", "Kierunek wiatru"],
  ["wiatr_predkosc", "Prędkość wiatru"]
];

function fmt(x) {
  if (!x) return {v:"—", u:""};
  if (x.wartosc !== undefined) return {v: String(x.wartosc), u: x.jednostka || ""};
  return {v: JSON.stringify(x), u:""};
}

function renderCards(data) {
  const grid = document.getElementById("grid");
  grid.innerHTML = sensors.map(([k, label]) => {
    const f = fmt(data[k]);
    const t = data[k]?.czas || "";
    const id = data[k]?.id || "";
    return `
      <div class="card">
        <div class="title">${label}</div>
        <div class="value">${f.v} <span style="font-size:16px;font-weight:400">${f.u}</span></div>
        <div class="meta">id: ${id || "—"}<br/>czas: ${t || "—"}</div>
      </div>
    `;
  }).join("");
}

const charts = {};

function makeChart(sensorKey, title) {
  const ctx = document.getElementById("ch_" + sensorKey);
  return new Chart(ctx, {
    type: "line",
    data: { labels: [], datasets: [{ label: title, data: [] }] },
    options: { responsive: true, animation: false, scales: { x: { display: false } } }
  });
}

async function refreshChart(sensorKey, title) {
  const res = await fetch(`/api/history/${sensorKey}?n=120`);
  const data = await res.json();
  const ch = charts[sensorKey];
  ch.data.labels = data.labels;
  ch.data.datasets[0].data = data.values;
  ch.data.datasets[0].label = `${title}${data.unit ? " (" + data.unit + ")" : ""}`;
  ch.update();
}

async function tick() {
  const res = await fetch("/api/latest");
  const data = await res.json();
  renderCards(data);

  for (const [k, title] of sensors) {
    await refreshChart(k, title);
  }
}

window.onload = () => {
  for (const [k, title] of sensors) charts[k] = makeChart(k, title);
  tick();
  setInterval(tick, 2000);
};
</script>
</body>
</html>
"""
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    t = threading.Thread(target=mqtt_loop, daemon=True)
    t.start()
    # dostępne z Windows: http://IP_LINUKSA:5000
    app.run(host="0.0.0.0", port=5000, debug=False)
