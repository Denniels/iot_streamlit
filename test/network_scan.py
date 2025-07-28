import os
import socket
import subprocess
from datetime import datetime

# Configuración
RANGO_IP = "192.168.0.1-192.168.0.254"  # Ajusta según tu red
PUERTOS = [22, 80, 502]  # SSH, HTTP, Modbus TCP
REPORTE_MD = "network_scan_report.md"

# Funciones

def ip_range(start, end):
    s = list(map(int, start.split(".")))
    e = list(map(int, end.split(".")))
    ips = []
    for i in range(s[3], e[3]+1):
        ips.append(f"{s[0]}.{s[1]}.{s[2]}.{i}")
    return ips

def ping(ip):
    try:
        output = subprocess.check_output(["ping", "-c", "1", "-W", "1", ip], stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def scan_ports(ip, ports):
    open_ports = []
    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(port)
        except Exception:
            pass
        finally:
            sock.close()
    return open_ports

def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "-"

def main():
    start_ip, end_ip = RANGO_IP.split("-")
    ips = ip_range(start_ip, end_ip)
    resultados = []
    for ip in ips:
        if ping(ip):
            hostname = get_hostname(ip)
            open_ports = scan_ports(ip, PUERTOS)
            resultados.append({
                "ip": ip,
                "hostname": hostname,
                "open_ports": open_ports,
                "bidirectional": True if open_ports else False
            })
    # Generar reporte Markdown
    with open(REPORTE_MD, "w", encoding="utf-8") as f:
        f.write(f"# Reporte de escaneo de red\n\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Rango escaneado: {RANGO_IP}\n\n")
        f.write("| IP | Hostname | Puertos abiertos | Comunicación bidireccional |\n")
        f.write("|----|----------|-----------------|---------------------------|\n")
        for r in resultados:
            puertos = ", ".join(str(p) for p in r["open_ports"]) if r["open_ports"] else "-"
            bidir = "Sí" if r["bidirectional"] else "No"
            f.write(f"| {r['ip']} | {r['hostname']} | {puertos} | {bidir} |\n")
    print(f"Reporte generado: {REPORTE_MD}")

if __name__ == "__main__":
    main()
