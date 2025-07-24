import os
import socket
import subprocess
from datetime import datetime
import ipaddress
import platform

REPORTE_MD = "network_scan_report.md"
PUERTOS = [22, 80, 502]  # SSH, HTTP, Modbus TCP

# Detecta la IP local y la subred

def get_local_ip():
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)

def get_subnet(ip):
    # Asume máscara /24
    net = ipaddress.ip_network(ip + '/24', strict=False)
    return [str(ip) for ip in net.hosts()]

def ping(ip):
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    try:
        output = subprocess.check_output(["ping", param, "1", ip], stderr=subprocess.DEVNULL)
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
    local_ip = get_local_ip()
    ips = get_subnet(local_ip)
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
        f.write(f"Subred escaneada: {local_ip}/24\n\n")
        f.write("| IP | Hostname | Puertos abiertos | Comunicación bidireccional |\n")
        f.write("|----|----------|-----------------|---------------------------|\n")
        for r in resultados:
            puertos = ", ".join(str(p) for p in r["open_ports"]) if r["open_ports"] else "-"
            bidir = "Sí" if r["bidirectional"] else "No"
            f.write(f"| {r['ip']} | {r['hostname']} | {puertos} | {bidir} |\n")
    print(f"Reporte generado: {REPORTE_MD}")

if __name__ == "__main__":
    main()
