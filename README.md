# Grafana Machine Charm

A Juju machine charm for deploying Grafana on bare metal, VMs, or LXD containers.

## Overview

This charm deploys Grafana, an open-source platform for monitoring and observability. It integrates seamlessly with Prometheus and other datasources through the `grafana_datasource` interface.

## Features

- ✅ Deploys Grafana on machine deployments (LXD, OpenStack, bare metal)
- ✅ Auto-configures Prometheus datasources via Juju relations
- ✅ Configurable HTTP port and admin credentials
- ✅ Automatic datasource provisioning
- ✅ Peer relation for password sharing across units
- ✅ Version management (default: 11.4.0)

## Quick Start

### Deploy Grafana

```bash
# Deploy Grafana
juju deploy ./grafana-machine_amd64.charm grafana

# Deploy Prometheus
juju deploy prometheus-machine prometheus

# Integrate Grafana with Prometheus
juju integrate grafana:grafana-source prometheus:grafana-source

# Get Grafana URL and credentials
juju status grafana
# Access at http://<grafana-ip>:3000
# Default username: admin
# Password: auto-generated (check grafana.ini or peer relation)
```

### Configuration Options

```bash
# Change HTTP port
juju config grafana http-port=8080

# Set custom admin credentials
juju config grafana admin-user=myadmin admin-password=mypassword

# Change Grafana version
juju config grafana grafana-version=11.3.0

# Set external URL (for reverse proxy setups)
juju config grafana external-url=https://grafana.example.com
```

## Architecture

### Components

- **Grafana Server**: Runs as systemd service (`grafana-server.service`)
- **Configuration**: `/etc/grafana/grafana.ini`
- **Data Directory**: `/var/lib/grafana/`
- **Logs**: `/var/log/grafana/`
- **Datasource Provisioning**: `/etc/grafana/provisioning/datasources/`

### Relations

#### `grafana-source` (requires)
- **Interface**: `grafana_datasource`
- **Purpose**: Consumes datasource configurations from providers like Prometheus
- **Auto-configures**: Datasources are automatically provisioned when relation is established

#### `grafana` (peer)
- **Interface**: `grafana_peers`
- **Purpose**: Shares admin password and other app-level data between units

## Integration with Prometheus

The charm uses the `GrafanaSourceConsumer` library to automatically configure Prometheus datasources:

1. **Establish Relation**: `juju integrate grafana:grafana-source prometheus:grafana-source`
2. **Auto-Configuration**: Prometheus provides its URL and metadata
3. **Provisioning**: Grafana creates datasource YAML in `/etc/grafana/provisioning/datasources/`
4. **Reload**: Grafana automatically loads the new datasource

Example provisioned datasource:
```yaml
apiVersion: 1
datasources:
- name: juju_<model>_<uuid>_prometheus_<unit>
  type: prometheus
  access: proxy
  url: http://<prometheus-ip>:9090
  isDefault: true
  editable: true
```

## Files and Directories

```
grafana-machine/
├── charmcraft.yaml           # Charm build configuration
├── config.yaml               # Configuration options schema
├── metadata.yaml             # Charm metadata and relations
├── requirements.txt          # Python dependencies
├── src/
│   └── charm.py             # Main charm logic
└── lib/
    ├── grafana_installer.py # Binary download and service setup
    ├── grafana_config.py    # Configuration file generation
    └── charms/
        └── grafana_k8s/v0/
            └── grafana_source.py  # Datasource relation library
```

## Development

### Build the Charm

```bash
charmcraft pack
```

### Testing

```bash
# Deploy test environment
juju add-model grafana-test
juju deploy ./grafana-machine_amd64.charm grafana

# Check status
juju status --relations

# View logs
juju debug-log --include grafana

# SSH to unit
juju ssh grafana/0
```

### Debugging

```bash
# Check Grafana service
juju ssh grafana/0 -- systemctl status grafana-server

# Check configuration
juju ssh grafana/0 -- cat /etc/grafana/grafana.ini

# Check datasources
juju ssh grafana/0 -- ls -la /etc/grafana/provisioning/datasources/
juju ssh grafana/0 -- cat /etc/grafana/provisioning/datasources/default.yaml

# Query Grafana API
juju ssh grafana/0 -- curl -s http://localhost:3000/api/health
juju ssh grafana/0 -- curl -s -u admin:<password> http://localhost:3000/api/datasources
```

## Deployment Scenarios

### Basic Deployment (Standalone)
```bash
juju deploy grafana
```

### With Prometheus Integration
```bash
juju deploy grafana
juju deploy prometheus
juju integrate grafana:grafana-source prometheus:grafana-source
```

### Behind Reverse Proxy
```bash
juju deploy grafana --config external-url=https://grafana.mycompany.com
# Configure your reverse proxy to forward to http://<grafana-ip>:3000
```

### High Availability (Multi-unit)
```bash
juju deploy grafana -n 3
# Note: Requires external database (not yet implemented)
```

## Verification

After deployment, verify the observability stack:

```bash
# 1. Check Grafana health
curl -s http://<grafana-ip>:3000/api/health | jq .

# 2. List datasources
curl -s -u admin:<password> http://<grafana-ip>:3000/api/datasources | jq .

# 3. Query metrics through Grafana
curl -s -u admin:<password> \
  'http://<grafana-ip>:3000/api/datasources/proxy/1/api/v1/query?query=up' | jq .
```

## Troubleshooting

### Grafana Won't Start
```bash
# Check logs
juju ssh grafana/0 -- journalctl -u grafana-server -n 50

# Check if binary exists
juju ssh grafana/0 -- ls -la /usr/local/grafana/bin/grafana

# Restart service
juju ssh grafana/0 -- sudo systemctl restart grafana-server
```

### No Datasources Configured
```bash
# Check relation status
juju status --relations

# Check if provider is publishing data
juju show-unit prometheus/0 --format=json | jq '.["prometheus/0"]["relation-info"]'

# Manually trigger config-changed
juju config grafana http-port=3000  # Set to same value to trigger
```

### Can't Access Grafana UI
```bash
# Check firewall
juju ssh grafana/0 -- sudo iptables -L

# Check if service is listening
juju ssh grafana/0 -- sudo netstat -tlnp | grep 3000

# Get admin password
juju ssh grafana/0 -- sudo grep admin_password /etc/grafana/grafana.ini
```

## Known Limitations

- HA mode requires external database (PostgreSQL/MySQL) - not yet implemented
- LDAP/OAuth integration not yet supported
- Plugin installation not automated
- No built-in backup/restore functionality

## Contributing

This charm is part of the Concourse CI observability stack. Contributions welcome!

## License

Apache 2.0
