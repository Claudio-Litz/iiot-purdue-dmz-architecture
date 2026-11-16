# Arquitetura de Referência IT/OT (Modelo Purdue & ISA/IEC 62443)

## 1. Visão Geral da Topologia
Este projeto implementa a convergência segura entre Tecnologia Operacional (OT) e Tecnologia da Informação (IT), segregando dispositivos de campo, gateways de borda, mensageria na DMZ e persistência historiadora em camadas isoladas.

## 2. Mapeamento dos Níveis (Purdue Enterprise Reference Architecture)

| Nível Purdue | Camada | Componente / Host | Protocolos & Portas | Função Técnica | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Nível 1** | Controle Básico | Simulador CLP (`simulador_clp.py`) / ESP32 | Modbus TCP (`5020/TCP`) | Geração/leitura determinística de registradores de processo (Holding Registers). | Implementado (Simulador) |
| **Nível 2** | Supervisão & Borda | Edge Gateway (`gateway_edge.py` - Windows) | Modbus TCP -> MQTT (`1883/TCP`) | Polling cíclico, análise de anomalias na borda e resiliência *Store-and-Forward* (SQLite). | Implementado |
| **Nível 3 (DMZ)** | Zona Desmilitarizada | Broker Eclipse Mosquitto (`iiots_mosquitto`) | MQTT (`1883/TCP`) | Desacoplamento *Pub/Sub*, autenticação obrigatória e autorização granular via ACL. | Implementado |
| **Nível 3 -> 3.5** | Ponte Segura | Serviço Ingestor (`iiots_ingestor` - Python) | MQTT -> PostgreSQL (`5432/TCP`) | Validação *Zero Trust* de schema JSON, sanitização e roteamento entre redes isoladas. | Implementado |
| **Nível 3.5 / 4** | Historiador Corporativo | Banco PostgreSQL 16 (`iiots_postgres`) | PostgreSQL (`5432/TCP` interno) | Armazenamento histórico estruturado em `JSONB` indexado e registro de eventos de alarme. | Implementado |

## 3. Segurança Aplicada no Fluxo Atual

### 3.1. Princípio do Menor Privilégio (ACL MQTT)
Cada entidade possui credencial dedicada e restrição estrita por tópico:
* `edge_windows`: Permissão exclusiva de escrita (`write`) em `planta/linha1/#`.
* `esp32_campo`: Permissão de escrita em `planta/servidor/telemetria` e `alarme`; leitura (`read`) apenas em `planta/servidor/comando/ventoinha`.
* `ihm_operador`: Leitura global de telemetria (`planta/#`) e escrita restrita a tópicos de comando.
* `ingestor_db`: Permissão exclusiva de leitura (`read`) em `planta/#` para persistência.

### 3.2. Isolamento de Redes Docker
* `dmz_ot_net`: Hospeda o Broker Mosquitto e recebe conexões da borda OT.
* `it_db_net`: Hospeda o PostgreSQL. Não possui roteamento direto para a rede OT.
* `iiots_ingestor`: Único container dual-homed autorizado a transitar dados entre `dmz_ot_net` e `it_db_net`, sem exposição de portas externas.

### 3.3. Resiliência de Borda (Store-and-Forward)
O Gateway de Borda mantém uma fila local persistente em SQLite (`buffer_edge.db`). Em caso de perda de conectividade com a DMZ, as leituras Modbus são enfileiradas localmente com timestamp UTC de origem e descarregadas cronologicamente após o restabelecimento do link.
