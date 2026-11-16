import os
import json
import logging
import psycopg2
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

MQTT_HOST = os.getenv("MQTT_HOST", "iiots_mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "ingestor_db")
MQTT_PASS = os.getenv("MQTT_PASS", "CHANGE_ME_MQTT_PASSWORD")

PG_HOST = os.getenv("PG_HOST", "iiots_postgres")
PG_DB = os.getenv("PG_DB", "iiots_historian")
PG_USER = os.getenv("PG_USER", "iiots_admin")
PG_PASS = os.getenv("PG_PASS", "CHANGE_ME_DB_PASSWORD")

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST, database=PG_DB, user=PG_USER, password=PG_PASS
    )

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logging.info("Conectado ao Broker MQTT na DMZ.")
        client.subscribe("planta/#", qos=1)
    else:
        logging.error(f"Falha na conexão MQTT. Código: {reason_code}")

def on_message(client, userdata, msg):
    topico = msg.topic
    try:
        raw_payload = msg.payload.decode("utf-8")
        dados = json.loads(raw_payload)
        if not isinstance(dados, dict):
            raise ValueError("Payload não é um objeto JSON válido.")
    except Exception as e:
        logging.warning(f"Payload rejeitado (Zero Trust) no tópico {topico}: {e}")
        return

    origem = dados.get("origem", topico.split("/")[1] if len(topico.split("/")) > 1 else "desconhecida")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if "alarme" in topico:
            severidade = str(dados.get("severidade", "ALTA"))[:20]
            mensagem = str(dados.get("mensagem", raw_payload))
            cur.execute(
                "INSERT INTO eventos_alarme (origem, severidade, mensagem) VALUES (%s, %s, %s)",
                (origem, severidade, mensagem)
            )
            logging.warning(f"ALARME GRAVADO [{severidade}] de {origem}: {mensagem}")
        else:
            cur.execute(
                "INSERT INTO telemetria_industrial (origem, topico, payload) VALUES (%s, %s, %s)",
                (origem, topico, json.dumps(dados))
            )
            logging.info(f"Telemetria gravada | Tópico: {topico} | Dados: {dados}")

        conn.commit()
        cur.close()
        conn.close()
    except Exception as db_err:
        logging.error(f"Erro ao persistir no PostgreSQL: {db_err}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ingestor_central_01")
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.on_connect = on_connect
client.on_message = on_message

logging.info("Iniciando serviço Ingestor IT/OT...")
client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
client.loop_forever()
