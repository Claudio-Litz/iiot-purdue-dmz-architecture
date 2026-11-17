# Purdue Reference Architecture & Data Flow Specification (ISA-95 / ISA-62443)

This document defines the topological segmentation, protocol translation boundaries, and security zones implemented in the `iiot-purdue-dmz-architecture` laboratory.

---

## 1. Architectural Overview

Industrial control systems (OT) operate under deterministic availability constraints and legacy protocols (such as Modbus TCP/RTU) that lack native encryption or authentication. Conversely, enterprise IT systems require relational persistence, high throughput, and strict access controls.

To bridge these domains securely without exposing Level 1/2 assets to the corporate network—or allowing compromised OT devices direct access to the Level 3 database—this architecture enforces a **Demilitarized Zone (DMZ)** coupled with a **Zero-Trust Ingestion Service**.

### 1.1 Purdue Model Layer Mapping

| Purdue Level | Zone / Conduit | Hardware Node | Software / Protocol Stack | Operational Role |
| :--- | :--- | :--- | :--- | :--- |
| **Level 0 / 1** | Field & Basic Control (OT) | ESP32 / Simulated PLC (`127.0.0.1:5020`) | C++ Firmware / Python `pymodbus` (Modbus TCP) | Generates deterministic physical/simulated process telemetry (oil temperature, hydraulic pressure, motor current) and executes closed-loop actuation. |
| **Level 2** | Supervisory & Edge Gateway (OT) | Windows Workstation (`192.168.1.66`) | Python `gateway_edge.py` + Local SQLite (`buffer_edge.db`) | Polls Level 1 Holding Registers (`FC=03`), evaluates local edge alarm rules, buffers payloads during network outages (*Store-and-Forward*), and publishes JSON over MQTT. |
| **Level 2.5** | Mobile HMI / Operations | Android Mobile Device (`192.168.1.68`) | IoT MQTT Panel (`ihm_operador`) | Subscribes to live plant telemetry (`planta/#`) and dispatches operator commands (`planta/servidor/comando/#`). |
| **Level 2.5 / 3** | Industrial DMZ Broker | `litzserver` (`192.168.1.200`) | Eclipse Mosquitto 2.x (`dmz_ot_net` bridge) | Decouples OT publishers from IT consumers using authenticated sessions (`PBKDF2-SHA512`) and topic-level Access Control Lists (`aclfile`). |
| **Level 3** | Operations Historian (IT) | `litzserver` (Isolated Bridge) | `iiots_ingestor` (Python) + PostgreSQL 16 (`it_db_net`) | Consumes DMZ MQTT topics, enforces JSON schema validation, prevents SQL injection via prepared statements, and persists time-series JSONB records. |

---

## 2. Network Isolation & Docker Bridge Topology

Within the central server (`litzserver`), container-level network segmentation prevents lateral movement:

* **`dmz_ot_net` (Docker Bridge):** Hosts `iiots_mosquitto` (mapped to `1883/tcp` and filtered via `iptables` `DOCKER-USER`) and the north-bound interface of `iiots_ingestor`.
* **`it_db_net` (Docker Bridge):** Hosts `iiots_postgres` and the south-bound interface of `iiots_ingestor`. External host access to port `5432/tcp` is dropped at the kernel perimeter (`! 172.16.0.0/12 -> DROP`).
