#!/usr/bin/env python3
"""
Probe pipeline end-to-end:
- lee dispositivos de la tabla `devices` (esp32/arduino_ethernet)
- prueba endpoint /data varias veces y mide tasa/latencia
- consulta la BD para contar filas en últimos 10 min y 60 min
- espera hasta el siguiente ciclo de adquisición (max 40s) para verificar que
  aparezcan nuevas filas en `sensor_data` (prueba end-to-end)

Uso: ejecutarlo con el Python del virtualenv `.iot_streamlit` del repo.
"""
import os
import time
import json
from datetime import datetime, timezone

import requests
import psycopg2

DB_NAME = os.getenv('DB_NAME', 'iot_db')
DB_USER = os.getenv('DB_USER', 'iot_user')
DB_PASS = os.getenv('DB_PASSWORD', 'DAms15820')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

DEFAULT_NETWORK_PREFIX = os.getenv('NETWORK_PREFIX', '192.168.0')


def db_connect():
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT)


def fetch_network_devices(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT device_id, device_type, ip_address, port, metadata, last_seen FROM devices WHERE device_type IN ('esp32_wifi','arduino_ethernet');")
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows


def probe_http(ip, port=80, path='/data', attempts=6, timeout=1.5):
    successes = 0
    latencies = []
    sample = None
    url = f'http://{ip}' if port == 80 else f'http://{ip}:{port}'
    url = url + path
    for i in range(attempts):
        try:
            start = time.time()
            r = requests.get(url, timeout=timeout)
            latency = time.time() - start
            if r.status_code == 200:
                try:
                    sample = r.json()
                except Exception:
                    sample = {'raw': r.text[:200]}
                successes += 1
                latencies.append(latency)
            else:
                pass
        except Exception:
            pass
        time.sleep(0.5)
    rate = successes / attempts if attempts else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else None
    return {'attempts': attempts, 'successes': successes, 'rate': rate, 'avg_latency': avg_latency, 'sample': sample}


def count_recent(conn, device_id, minutes=10):
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sensor_data WHERE device_id = %s AND timestamp >= NOW() - INTERVAL '%s minutes';", (device_id, minutes))
        return cur.fetchone()[0]


def latest_timestamp(conn, device_id):
    with conn.cursor() as cur:
        cur.execute("SELECT MAX(timestamp) FROM sensor_data WHERE device_id = %s;", (device_id,))
        res = cur.fetchone()[0]
    return res


def discover_on_network(target_device_id, prefix=DEFAULT_NETWORK_PREFIX, ports=(80, 8080), timeout=0.7):
    # Scanea la subred en busca de /data que reporte el device_id
    for i in range(1, 255):
        ip = f"{prefix}.{i}"
        for port in ports:
            try:
                url = f'http://{ip}' if port == 80 else f'http://{ip}:{port}'
                url = url + '/data'
                r = requests.get(url, timeout=timeout)
                if r.status_code == 200:
                    try:
                        j = r.json()
                        if j.get('device_id') == target_device_id:
                            return {'ip': ip, 'port': port, 'sample': j}
                    except Exception:
                        continue
            except Exception:
                continue
    return None


def human(dt):
    if dt is None:
        return 'None'
    if isinstance(dt, str):
        return dt
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def main():
    print('=== PIPELINE PROBE ===')
    conn = db_connect()
    devices = fetch_network_devices(conn)
    print(f'Dispositivos encontrados: {len(devices)}')

    summary = []

    for d in devices:
        device_id = d.get('device_id')
        device_type = d.get('device_type')
        ip = d.get('ip_address')
        port = int(d.get('port') or 80)
        print('\n--- Device:', device_id, f'(type={device_type}) ip={ip} port={port}')

        if not ip:
            print('Sin ip registrada: intentando descubrimiento en la red...')
            found = discover_on_network(device_id)
            if found:
                ip = found['ip']
                port = found.get('port', 80)
                print('Encontrado en red:', ip, 'port', port)
            else:
                print('No encontrado en red, se saltará probe HTTP')

        probe = None
        if ip:
            probe = probe_http(ip, port=port, attempts=6, timeout=1.2)
            print('Endpoint probe:', f"attempts={probe['attempts']} successes={probe['successes']} rate={probe['rate']:.2f} avg_latency={probe['avg_latency']}")
            print('Sample ejemplo:', json.dumps(probe['sample'], default=str)[:400])

        # contadores en BD
        db10 = count_recent(conn, device_id, minutes=10)
        db60 = count_recent(conn, device_id, minutes=60)
        latest_before = latest_timestamp(conn, device_id)
        print(f'DB: last 10 min = {db10}, last 60 min = {db60}, latest = {human(latest_before)}')

        # Esperar el siguiente ciclo de adquisición (máx 40s) para ver si aparecen filas nuevas
        print('Esperando hasta 40s para verificar inserción tras siguiente poll de adquisición...')
        start_wait = time.time()
        found_new = False
        while time.time() - start_wait < 40:
            time.sleep(5)
            latest_after = latest_timestamp(conn, device_id)
            if latest_after and (not latest_before or latest_after > latest_before):
                print('Nueva fila detectada en BD:', human(latest_after))
                found_new = True
                break
        if not found_new:
            print('No se detectaron nuevas filas en el periodo de espera (adquisición puede no estar leyendo este dispositivo).')

        summary.append({'device_id': device_id, 'ip': ip, 'probe': probe, 'db10': db10, 'db60': db60, 'new_data_seen': found_new})

    # resumen compacto
    print('\n=== RESUMEN COMPACTO ===')
    total_10 = sum(s['db10'] for s in summary)
    print('TOTAL registros DB (últimos 10 min) para redes:', total_10)
    for s in summary:
        pid = s['device_id']
        ip = s['ip']
        probe = s['probe']
        rate = probe['rate'] if probe else None
        print(f"{pid} ip={ip} db10={s['db10']} db60={s['db60']} probe_rate={rate} new_data_seen={s['new_data_seen']}")

    conn.close()


if __name__ == '__main__':
    main()
