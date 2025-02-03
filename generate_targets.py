#!/usr/bin/env python3
import docker
import json
import time
import os
import logging
import hashlib

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

DOCKER_SOCKET = 'unix://var/run/docker.sock'
TARGET_FILE = "/app/targets/docker.json"
SCAN_INTERVAL = 5  
PROM_LABEL = "prometheus.scrape"
PROM_PORT_LABEL = "prometheus.port"
DEFAULT_PORT = "80" 
TARGET_NETWORK = "monitoring"  

def generate_targets():
    client = docker.DockerClient(base_url=DOCKER_SOCKET)
    targets = []
    try:
        containers = client.containers.list()
    except Exception as e:
        logging.error("Error listing containers: %s", e)
        return targets

    found_containers = []

    for container in containers:
        labels = container.labels

        if labels.get(PROM_LABEL, "").lower() != "true":
            continue

        port = labels.get(PROM_PORT_LABEL, DEFAULT_PORT)

        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        if TARGET_NETWORK not in networks:
            logging.debug("Container '%s' is not attached to network '%s'.", container.name, TARGET_NETWORK)
            continue

        network_info = networks[TARGET_NETWORK]

        dns_aliases = network_info.get("Aliases")
        if dns_aliases and len(dns_aliases) > 0:
            dns_name = dns_aliases[0]
        else:
            dns_name = container.name

        target_entry = {
            "targets": [f"{dns_name}:{port}"],
            "labels": {
                "container_name": container.name,
                "job": labels.get("prometheus.job", container.name),
                "metrics_path": labels.get("prometheus.metrics_path", "/metrics")
            }
        }
        targets.append(target_entry)
        found_containers.append(container.name)
        logging.info("Found container for scraping: '%s' -> target: %s:%s", container.name, dns_name, port)

    if not found_containers:
        logging.info("No containers found for scraping with label '%s'.", PROM_LABEL)
    else:
        logging.info("Total containers found for scraping: %d", len(found_containers))

    return targets

def write_targets_atomically(targets):
    new_content = json.dumps(targets, indent=2)
    new_hash = hashlib.md5(new_content.encode('utf-8')).hexdigest()

    if os.path.exists(TARGET_FILE):
        try:
            with open(TARGET_FILE, "r") as f:
                old_content = f.read()
            old_hash = hashlib.md5(old_content.encode('utf-8')).hexdigest()
            if new_hash == old_hash:
                logging.info("No changes in targets; skipping file update.")
                return
        except Exception as e:
            logging.warning("Could not read existing target file: %s", e)

    temp_file = TARGET_FILE + ".tmp"
    try:
        with open(temp_file, "w") as f:
            f.write(new_content)
        os.replace(temp_file, TARGET_FILE)
        logging.info("Atomically updated %s with %d targets.", TARGET_FILE, len(targets))
    except Exception as e:
        logging.error("Error during atomic file update: %s", e)

def main():
    logging.info("Starting target generation. Writing to: %s", TARGET_FILE)
    while True:
        try:
            targets = generate_targets()
            write_targets_atomically(targets)
        except Exception as err:
            logging.error("Error during target generation: %s", err)
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
