import serial.tools.list_ports
import psutil
import socket
from datetime import datetime

# Generar nombre de archivo único por fecha/hora
reporte_md = f"device_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

resultados = []

print("=== Dispositivos conectados por USB/Serie ===")
resultados.append("# Dispositivos conectados por USB/Serie\n")
for port in serial.tools.list_ports.comports():
    linea = f"Puerto: {port.device} | Descripción: {port.description}"
    print(linea)
    resultados.append(f"- {linea}\n")
if not list(serial.tools.list_ports.comports()):
    print("No se detectaron dispositivos USB/serie.")
    resultados.append("No se detectaron dispositivos USB/serie.\n")

print("\n=== Conexiones de red activas hacia este equipo ===")
resultados.append("\n# Conexiones de red activas hacia este equipo\n")
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
print(f"IP local detectada: {local_ip}\n")
resultados.append(f"IP local detectada: {local_ip}\n\n")

conexiones = 0
for conn in psutil.net_connections(kind='inet'):
    if conn.status == 'ESTABLISHED' and conn.laddr.ip == local_ip:
        linea = f"Desde: {conn.raddr.ip}:{conn.raddr.port} -> Puerto local: {conn.laddr.port} | Protocolo: {conn.type}"
        print(linea)
        resultados.append(f"- {linea}\n")
        conexiones += 1
if conexiones == 0:
    print("No se detectaron conexiones de red activas hacia este equipo.")
    resultados.append("No se detectaron conexiones de red activas hacia este equipo.\n")

print("\nFin del escaneo. Reporte guardado en:", reporte_md)

with open(reporte_md, "w", encoding="utf-8") as f:
    f.writelines(resultados)
