import time
import json
import sqlite3
import logging
from datetime import datetime, timezone
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [EDGE-GW] %(message)s")

# CONFIGURAÇÕES (Ajuste o IP do litzserver)
LITZSERVER_IP = "192.168.X.X"
MQTT_PORT = 1883
MQTT_USER = "edge_windows"
MQTT_PASS = "CHANGE_ME_EDGE_PASSWORD"

MODBUS_HOST = "127.0.0.1"
MODBUS_PORT = 5020

TOPICO_TELEMETRIA = "planta/linha1/prensa01"
TOPICO_ALARME = "planta/linha1/prensa01/alarme"

# Inicializa banco SQLite local para Store-and-Forward (resiliência offline)
def init_buffer_db():
    conn = sqlite3.connect("buffer_edge.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fila_envio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topico TEXT NOT NULL,
            payload TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

buffer_conn = init_buffer_db()
mqtt_conectado = False

def on_connect(client, userdata, flags, reason_code, properties):
    global mqtt_conectado
    if reason_code == 0:
        mqtt_conectado = True
        logging.info("Conectado ao Broker MQTT na DMZ.")
    else:
        mqtt_conectado = False
        logging.error(f"Falha na conexão MQTT: {reason_code}")

def on_disconnect(client, userdata, flags, reason_code, properties):
    global mqtt_conectado
    mqtt_conectado = False
    logging.warning("Desconectado do Broker MQTT! Ativando modo Store-and-Forward (buffer local).")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gateway_edge_win01")
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_disconnect = on_disconnect

try:
    client.connect_async(LITZSERVER_IP, MQTT_PORT, keepalive=30)
    client.loop_start()
except Exception as e:
    logging.error(f"Erro inicial de rede: {e}")

def enviar_ou_enfileirar(topico, dados_dict):
    payload_str = json.dumps(dados_dict)
    if mqtt_conectado:
        info = client.publish(topico, payload_str, qos=1)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            logging.info(f"Publicado -> [{topico}] {payload_str}")
            return
    # Se offline ou falha no envio, salva no SQLite local
    buffer_conn.execute(
        "INSERT INTO fila_envio (topico, payload, criado_em) VALUES (?, ?, ?)",
        (topico, payload_str, datetime.now(timezone.utc).isoformat())
    )
    buffer_conn.commit()
    logging.warning(f"OFFLINE -> Dado retido no buffer SQLite: {payload_str}")

def descarregar_buffer():
    if not mqtt_conectado:
        return
    cur = buffer_conn.cursor()
    cur.execute("SELECT id, topico, payload FROM fila_envio ORDER BY id ASC LIMIT 50")
    pendentes = cur.fetchall()
    if pendentes:
        logging.info(f"Descarregando {len(pendentes)} mensagens retidas no buffer...")
        for row_id, topico, payload in pendentes:
            info = client.publish(topico, payload, qos=1)
            if info.rc == mqtt.MQTT_ERR_SUCCESS:
                buffer_conn.execute("DELETE FROM fila_envio WHERE id = ?", (row_id,))
                buffer_conn.commit()
            else:
                break

modbus_client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)

while True:
    descarregar_buffer()

    if not modbus_client.connected:
        modbus_client.connect()

    rr = modbus_client.read_holding_registers(address=0, count=3, slave=1)
    if not rr.isError():
        temp_oleo = rr.registers[0] / 10.0
        pressao_bar = rr.registers[1]
        corrente_a = rr.registers[2] / 10.0

        telemetria = {
            "origem": "prensa_01_modbus",
            "timestamp_edge": datetime.now(timezone.utc).isoformat(),
            "temperatura_oleo": temp_oleo,
            "pressao_bar": pressao_bar,
            "corrente_motor_a": corrente_a
        }
        enviar_ou_enfileirar(TOPICO_TELEMETRIA, telemetria)

        # Regra de Edge Analytics: detecção local de anomalia
        if temp_oleo > 70.0 or pressao_bar > 175:
            alarme = {
                "origem": "prensa_01_modbus",
                "severidade": "CRITICA",
                "mensagem": f"Limite excedido na Prensa 01! Temp: {temp_oleo}°C | Pressão: {pressao_bar} bar"
            }
            enviar_ou_enfileirar(TOPICO_ALARME, alarme)
    else:
        logging.error("Falha ao ler registradores do CLP Modbus local.")

    time.sleep(2)