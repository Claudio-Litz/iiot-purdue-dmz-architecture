import time
import random
import threading
import logging
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CLP-MODBUS] %(message)s")

# Inicializa 10 Holding Registers (HR[0]=Temp*10, HR[1]=Pressao, HR[2]=Corrente*10)
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [480, 125, 142, 0, 0, 0, 0, 0, 0, 0])
)
context = ModbusServerContext(slaves=store, single=True)

def atualizar_processo():
    temp = 48.0
    pressao = 125
    corrente = 14.2

    while True:
        # Simula variação realista com chance ocasional de pico térmico (para testar alarme)
        temp += random.uniform(-1.5, 2.2)
        if temp > 76.0:
            temp = 52.0  # Simula resfriamento após pico
        elif temp < 42.0:
            temp = 44.0

        pressao = max(110, min(182, pressao + random.randint(-5, 6)))
        corrente = round(max(11.0, min(24.0, corrente + random.uniform(-0.8, 0.9))), 1)

        # Modbus trafega inteiros de 16 bits: multiplicamos decimais por 10
        valores = [int(temp * 10), int(pressao), int(corrente * 10)]
        context[0].setValues(3, 0, valores)  # Function Code 3 (Holding Registers), endereço 0

        logging.info(f"Registradores atualizados -> Temp: {temp:.1f}°C | Pressão: {pressao} bar | Corrente: {corrente:.1f}A")
        time.sleep(2)

if __name__ == "__main__":
    t = threading.Thread(target=atualizar_processo, daemon=True)
    t.start()
    logging.info("Servidor Modbus TCP iniciado em 127.0.0.1:5020...")
    StartTcpServer(context=context, address=("127.0.0.1", 5020))