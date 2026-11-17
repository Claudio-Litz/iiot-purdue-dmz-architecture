# Network Segmentation (Firewall) & Access Control Matrix (ACL)

This specification details the L3/L4 packet filtering policies and L7 MQTT topic authorization rules enforced across the **Industrial DMZ** and **IT Historian** zones in compliance with the **ISA/IEC 62443** *Least Privilege* principle.

---

## 1. L3/L4 Perimeter Rules (iptables DOCKER-USER Chain)

Because Docker manipulates `netfilter` via `DNAT` in the `PREROUTING` chain, standard host `INPUT` rules do not intercept traffic routed to published container ports. All perimeter filtering is therefore enforced inside the `DOCKER-USER` chain, which the Linux kernel evaluates prior to Docker's internal bridge chains:

| Rule # | Protocol / Port | Source IP | Destination Service | Target Action | Architectural Justification (ISA/IEC 62443) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `TCP / 1883` | `172.16.0.0/12` | `iiots_mosquitto` | `ACCEPT` | Permits internal Docker bridge containers (`iiots_ingestor`) to consume DMZ broker topics. |
| **2** | `TCP / 1883` | `192.168.1.68` | `iiots_mosquitto` | `ACCEPT` | Whitelists the authorized **Level 2.5 Mobile HMI** terminal. |
| **3** | `TCP / 1883` | `! 192.168.1.66` | `iiots_mosquitto` | `DROP` | Drops connection attempts from all other external hosts except the authorized **Level 2 Edge Gateway (`192.168.1.66`)**. |
| **4** | `TCP / 5432` | `! 172.16.0.0/12` | `iiots_postgres` | `DROP` | **Strict OT/IT Isolation:** Blocks all direct external access from the LAN/OT network to the PostgreSQL historian. |
| **5** | `ALL` | `0.0.0.0/0` | `0.0.0.0/0` | `RETURN` | Returns non-industrial host traffic to default processing chains. |

---

## 2. L7 MQTT Topic Access Control List (aclfile)

Every client passing the L3/L4 IP whitelist must authenticate with unique credentials (`PBKDF2-SHA512`) and is restricted by the Mosquitto `aclfile` to prevent spoofing or unauthorized actuation:

| Identity (Username) | Purdue Level | MQTT Topic Pattern | Permission | Operational Scope |
| :--- | :--- | :--- | :--- | :--- |
| `esp32_campo` | Level 1 (Field) | `planta/servidor/telemetria`<br>`planta/servidor/alarme`<br>`planta/servidor/comando/ventoinha` | `write`<br>`write`<br>`read` | Publishes physical sensor telemetry/alarms and subscribes strictly to cooling fan actuation commands. |
| `edge_windows` | Level 2 (Edge Gateway) | `planta/linha1/#` | `write` | Write-only access to publish Modbus TCP telemetry and alarms from Hydraulic Press 01. Cannot read topics or issue commands. |
| `ihm_operador` | Level 2.5 (Mobile HMI) | `planta/#`<br>`planta/servidor/comando/#` | `read`<br>`write` | Global read visibility for supervision and write access restricted to operator command topics. |
| `ingestor_db` | Level 3 (Historian Service) | `planta/#` | `read` | Read-only consumer across all plant topics for schema validation and PostgreSQL persistence. |
