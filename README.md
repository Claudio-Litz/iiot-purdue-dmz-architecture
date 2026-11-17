# Industrial IIoT & OT/IT Convergence Lab (Purdue Model / ISA-62443)

An end-to-end **Operational Technology (OT) / Information Technology (IT)** convergence architecture implementing the **Purdue Reference Model (ISA-95 / ISA-62443)**. This project demonstrates deterministic Modbus TCP polling at the edge, offline-resilient **Store-and-Forward** buffering (SQLite), authenticated DMZ message brokering (Mosquitto MQTT with strict ACLs), Zero-Trust payload ingestion (Python), relational time-series persistence (PostgreSQL `JSONB`), and kernel-level perimeter segmentation (`iptables` `DOCKER-USER`).

---

## 1. System Architecture (Purdue Model)

* **Level 0 / 1 — Field & Control (`simulador_clp.py` / ESP32):** Simulates an industrial hydraulic press PLC over **Modbus TCP (`127.0.0.1:5020`)**, exposing Holding Registers for oil temperature, hydraulic pressure (bar), and motor current (A), alongside physical sensor/relay integration on ESP32.
* **Level 2 — Edge Gateway (`gateway_edge.py` on Windows `192.168.1.66`):** Polls Modbus registers every 2 seconds, evaluates local edge threshold rules (generating immediate `CRITICA` alarms when temperature exceeds `70.0°C` or pressure exceeds `175 bar`), and publishes structured JSON telemetry to the DMZ[cite: 10]. Includes a local **SQLite Store-and-Forward engine (`buffer_edge.db`)** to guarantee **Zero Data Loss** during network outages[cite: 9, 10].
* **Level 2.5 — Mobile HMI (`192.168.1.68`):** Authorized operator dashboard (IoT MQTT Panel) subscribing to live plant telemetry and issuing manual override commands[cite: 2, 5, 6].
* **Level 2.5 / 3 — Industrial DMZ (`iiots_mosquitto` on `litzserver` `192.168.1.200`):** Eclipse Mosquitto 2.x broker isolated in the `dmz_ot_net` Docker bridge. Enforces `PBKDF2-SHA512` authentication (`allow_anonymous false`) and strict per-topic read/write privileges (`aclfile`).
* **Level 3 — Historian & Zero-Trust Ingestor (`iiots_ingestor` + `iiots_postgres`):** Python ingestion microservice bridging `dmz_ot_net` and `it_db_net`. Validates JSON schemas, neutralizes SQL injection attempts, and persists telemetry (`JSONB` with GIN indexing) and alarms into PostgreSQL 16.

---

## 2. Repository Structure

    iiot-purdue-dmz-architecture/
    ├── README.md
    ├── docs/
    │   ├── 01-purdue-architecture.md         # Topological specification & Docker bridge isolation
    │   ├── 02-firewall-acl-matrix.md         # Formal L3/L4 iptables rules & L7 MQTT ACL matrix
    │   ├── 03-intrusion-resilience-tests.md  # Empirical audit logs, SQLi defense & Store-and-Forward proofs
    │   └── evidencias/                       # Raw firewall logs, DB queries & validation screenshots
    ├── edge-gateway-windows/
    │   ├── simulador_clp.py                  # Level 1 Modbus TCP PLC simulator
    │   ├── gateway_edge.py                   # Level 2 Edge Gateway with SQLite Store-and-Forward
    │   └── requirements.txt
    ├── ingestor-service/
    │   ├── ingestor.py                       # Level 3 Zero-Trust MQTT-to-PostgreSQL consumer
    │   ├── Dockerfile
    │   └── requirements.txt
    └── server-dmz-docker/
        ├── docker-compose.yml                # Multi-network container orchestration (dmz_ot_net / it_db_net)
        ├── mosquitto/config/
        │   ├── mosquitto.conf
        │   ├── aclfile                       # Least-privilege topic access control list
        │   └── passwd.example
        └── postgres/
            └── init.sql                      # JSONB telemetry & alarm tables with GIN indexes

---

## 3. Key Security & Resilience Validations

1. **L3/L4 Perimeter Segmentation (`DOCKER-USER`):** Direct access from the OT LAN to the PostgreSQL historian (`5432/tcp`) is dropped at the Linux kernel level (`! 172.16.0.0/12 -> DROP`). Access to the MQTT Broker (`1883/tcp`) is strictly whitelisted to the Edge Gateway (`192.168.1.66`) and Mobile HMI (`192.168.1.68`).
2. **Zero-Trust Payload Sanitization:** Malformed strings and SQL injection payloads (`DROP TABLE telemetria_industrial;--`) injected into MQTT topics are caught and discarded by `ingestor.py` prior to database transaction execution.
3. **Store-and-Forward Fault Tolerance:** During simulated firewall lockdowns, `gateway_edge.py` seamlessly switches to local SQLite buffering (`fila_envio`) and automatically drains the historical backlog upon reconnection[cite: 9, 10].

For full technical specifications, packet counter logs, and test evidence, see the [`docs/`](./docs/) directory.
