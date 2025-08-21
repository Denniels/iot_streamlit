#!/usr/bin/env python3
"""
Comprobación end-to-end del pipeline IoT:
- Obtener dispositivos desde la base de datos
- Probar endpoints /data en los IPs reportados varias veces (mide éxito y latencias)
- Consultar la base de datos para contar filas últimas 10 min / 1 h
- Consultar la API (local o CF) para validar que devuelve los datos recientes

Salida: resumen por dispositivo para decidir siguientes pasos.

Uso: python3 tools/run_pipeline_checks.py
"""

import os
import sys
import time
import requests
from collections import defaultdict
from datetime import datetime

# Asegurar que el repo root esté en sys.path para poder importar backend
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Intentar reutilizar el cliente del proyecto para acceder a la BD
try:
    from backend.db_writer import LocalPostgresClient
except Exception as e:
    print(f"Error importando LocalPostgresClient: {e}")
    LocalPostgresClient = None


def get_api_base():
    # Prefer ENV override
    api_env = os.getenv('API_URL')
    if api_env:
        return api_env.rstrip('/')

    # Intentar punto local conocido
    local_try = 'http://localhost:8000'
    try:
        r = requests.get(f'{local_try}/cf_url', timeout=2)
        if r.status_code == 200:
            j = r.json()
            if j.get('success') and j.get('cf_url'):
                return j['cf_url'].rstrip('/')
    except Exception:
        pass

    # Fallback a localhost
    return local_try


def poll_device_endpoint(ip, port=80, path='/data', duration=60, interval=5):
    """Poll the device endpoint periodically and return stats."""
    url = f'http://{ip}:{port}{path}' if port and port != 80 else f'http://{ip}{path}'
    end = time.time() + duration
    attempts = 0
    successes = 0
    latencies = []
    payloads_sample = []

    while time.time() < end:
        attempts += 1
        t0 = time.time()
        try:
            r = requests.get(url, timeout=3)
            elapsed = time.time() - t0
            if r.status_code == 200:
                successes += 1
                latencies.append(elapsed)
                try:
                    payload = r.json()
                except Exception:
                    payload = r.text[:200]
                if len(payloads_sample) < 3:
                    payloads_sample.append(payload)
        except Exception:
            pass
        time.sleep(interval)

    return {
        'url': url,
        'attempts': attempts,
        'successes': successes,
        'success_rate': successes / attempts if attempts else 0,
        'avg_latency_s': (sum(latencies) / len(latencies)) if latencies else None,
        'samples': payloads_sample
    }


def db_counts(client, minutes=10):
    q = """
        SELECT device_id, COUNT(*) AS cnt, MIN(timestamp) AS first_ts, MAX(timestamp) AS last_ts
        FROM sensor_data
        WHERE timestamp >= NOW() - INTERVAL '%s minutes'
        GROUP BY device_id
    """ % minutes
    try:
        rows = client.execute_query(q)
        return {r['device_id']: r for r in rows}
    except Exception as e:
        print(f"Error ejecutando query de conteo {e}")
        return {}


def api_get_data(api_base, device_id, hours=0.17):
    url = f"{api_base}/data/{device_id}"
    try:
        r = requests.get(url, params={'hours': hours}, timeout=5)
        if r.status_code == 200:
            j = r.json()
            # Se espera que el endpoint devuelva una lista o dict con 'data'
            # Manejar ambos casos
            if isinstance(j, dict) and j.get('data'):
                data = j['data']
            elif isinstance(j, list):
                data = j
            elif isinstance(j, dict) and j.get('rows'):
                data = j['rows']
            else:
                # Intentar inferir keys que contengan registros
                data = j
            count = len(data) if hasattr(data, '__len__') else 1
            return {'ok': True, 'status': r.status_code, 'count': count, 'raw': j}
        else:
            return {'ok': False, 'status': r.status_code, 'text': r.text}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def main():
    print("=== RUN PIPELINE CHECKS ===")

    if LocalPostgresClient is None:
        print("No se pudo importar LocalPostgresClient. Asegurate de ejecutar desde el entorno del proyecto.")
        return

    client = LocalPostgresClient()

    devices = client.get_devices()
    print(f"Dispositivos en BD: {len(devices)}")

    # Filtrar dispositivos de red
    network_devices = [d for d in devices if d.get('device_type') in ('esp32_wifi', 'arduino_ethernet')]
    print(f"Dispositivos de red (esp32/arduino_eth): {len(network_devices)}\n")

    api_base = get_api_base()
    print(f"API base: {api_base}\n")

    summary = {}

    # DB counts
    counts_10 = db_counts(client, minutes=10)
    counts_60 = db_counts(client, minutes=60)

    for d in network_devices:
        did = d.get('device_id')
        ip = d.get('ip_address')
        port = d.get('port') or 80
        # ip may be inet type; coerce to string
        ip_str = str(ip) if ip else None

        print(f"--- Device: {did} (type={d.get('device_type')}) ip={ip_str} port={port}")

        probe_result = None
        if ip_str:
            probe_result = poll_device_endpoint(ip_str, port=int(port) if port else 80, duration=30, interval=5)
            print(f"Endpoint probe: attempts={probe_result['attempts']} successes={probe_result['successes']} rate={probe_result['success_rate']:.2f} avg_latency={probe_result['avg_latency_s']}")
            if probe_result['samples']:
                print(f"Samples ejemplo: {probe_result['samples'][0]}")
        else:
            print("Sin ip registrada: salto probe")

        db10 = counts_10.get(did)
        db60 = counts_60.get(did)
        cnt10 = int(db10['cnt']) if db10 else 0
        cnt60 = int(db60['cnt']) if db60 else 0
        print(f"DB: last 10 min = {cnt10}, last 60 min = {cnt60}")

        api_res = api_get_data(api_base, did, hours=0.17)
        if api_res.get('ok'):
            print(f"API: returned {api_res['count']} rows for last 10 min")
        else:
            print(f"API: error - {api_res}")

        summary[did] = {
            'ip': ip_str,
            'probe': probe_result,
            'db_10min': cnt10,
            'db_60min': cnt60,
            'api': api_res
        }

        print('\n')

    # Global overview
    total_10 = sum(v['db_10min'] for v in summary.values())
    print(f"TOTAL registros en DB (últimos 10 min) para redes: {total_10}")

    # Print summary compact
    print('\n=== COMPACT SUMMARY ===')
    for did, info in summary.items():
        pr = info['probe']
        rate = pr['success_rate'] if pr else None
        print(f"{did} ip={info['ip']} db10={info['db_10min']} db60={info['db_60min']} probe_success_rate={rate} api_ok={info['api'].get('ok')}")

    print('\n=== FIN ===')


if __name__ == '__main__':
    main()
