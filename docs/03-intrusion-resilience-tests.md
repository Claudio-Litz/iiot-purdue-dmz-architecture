# Validation Report: Perimeter Hardening, Zero-Trust Ingestion & Store-and-Forward Resilience

This report documents the empirical validation tests conducted across the **Level 2 Edge Gateway (`192.168.1.66`)**, **Level 2.5 Mobile HMI (`192.168.1.68`)**, and **Level 3 DMZ/Historian Server (`192.168.1.200`)**[cite: 5, 9, 10].

---

## 1. Perimeter Hardening & Database Isolation Audit

### 1.1 Pre-Hardening Baseline (Vulnerability Exposure)
Prior to configuring the `DOCKER-USER` chain, TCP port scans executed from the Windows Edge workstation (`192.168.1.66`) confirmed that both the MQTT Broker (`1883/tcp`) and the PostgreSQL Historian (`5432/tcp`) returned `TcpTestSucceeded: True`. Furthermore, unwhitelisted wireless devices could establish TCP sockets directly with the DMZ broker.

### 1.2 Post-Hardening Kernel Verification
After applying the source-IP filtering policy, kernel packet counters (`iptables -L DOCKER-USER -v -n --line-numbers`) confirmed active perimeter enforcement:

    Chain DOCKER-USER (1 references)
    num   pkts bytes target     prot opt in     out     source               destination         
    1        0     0 ACCEPT     tcp  --  *      *       172.16.0.0/12        0.0.0.0/0            tcp dpt:1883
    2        0     0 ACCEPT     tcp  --  *      *       192.168.1.68         0.0.0.0/0            tcp dpt:1883
    3       47  2784 DROP       tcp  --  *      *      !192.168.1.66         0.0.0.0/0            tcp dpt:1883
    4       10   520 DROP       tcp  --  *      *      !172.16.0.0/12        0.0.0.0/0            tcp dpt:5432
    5     3843  632K RETURN     all  --  *      *       0.0.0.0/0            0.0.0.0/0

* **Rule 3 (`47 packets / 2,784 bytes dropped`):** Connection attempts to `1883/tcp` from non-whitelisted hosts (prior to whitelisting `192.168.1.68` in Rule 2) were silently dropped at the network layer, even when valid MQTT credentials (`ihm_operador`) were supplied[cite: 2, 5].
* **Rule 4 (`10 packets / 520 bytes dropped`):** Direct connection attempts from the OT network (`192.168.1.66`) to the PostgreSQL database (`5432/tcp`) were blocked (`TcpTestSucceeded: False`), enforcing strict conduit isolation.

---

## 2. Malformed Payload & SQL Injection Defense (Zero-Trust Ingestor)

To verify that a compromised Edge credential cannot corrupt or drop the Level 3 database, a raw SQL injection payload was published directly to an authorized topic:

    docker exec -it iiots_mosquitto mosquitto_pub -u edge_windows -P <REDACTED> -t "planta/linha1/prensa01" -m "DROP TABLE telemetria_industrial;--"

**Audit Result:**
1. The `iiots_ingestor` service intercepted the message and rejected it during strict JSON schema deserialization (`json.loads` + `isinstance(dados, dict)` validation) before opening a database cursor.
2. All valid JSON payloads are inserted exclusively via parameterized `psycopg2` queries (`INSERT INTO telemetria_industrial (origem, topico, payload) VALUES (%s, %s, %s)`), neutralizing second-order SQL injection vectors.

---

## 3. Network Outage Simulation & Store-and-Forward Recovery

Industrial environments require **Zero Data Loss** during transient WAN/LAN outages or firewall lockdowns between Level 2 and Level 3.

### 3.1 Fault Injection Procedure
While `simulador_clp.py` (Modbus TCP server on `127.0.0.1:5020`) and `gateway_edge.py` were actively polling Hydraulic Press 01 every 2 seconds, a link cut was simulated on `litzserver` by dropping all external traffic to port `1883/tcp`:

    sudo iptables -I DOCKER-USER 1 -p tcp --dport 1883 ! -s 172.16.0.0/12 -j DROP

### 3.2 Empirical Results
1. **Autonomous Offline Buffering (`docs/evidencias/img-01-store-forward-offline.png`):**
   * `gateway_edge.py` detected the broker disconnection callback and immediately routed all polled Modbus registers—including critical high-pressure alarms (`178 bar > 175 bar threshold`)—into the local transactional SQLite database (`buffer_edge.db`, table `fila_envio`), preserving the exact edge acquisition timestamp (`timestamp_edge` in UTC)[cite: 10].
2. **Automatic Queue Synchronization (`docs/evidencias/img-02-store-forward-recovery.png`):**
   * Upon removing the simulated outage rule (`sudo iptables -D DOCKER-USER 1`), the gateway re-established the MQTT session, sequentially drained all buffered records (`Descarregando 14 mensagens retidas no buffer...`) with `QoS 1`, and purged the local SQLite queue back to `Rows: 0` without losing a single sample[cite: 9].
