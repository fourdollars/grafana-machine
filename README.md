# Grafana Machine Charm

A Juju machine charm for deploying Grafana on bare metal, VMs, or LXD containers.

## Features

- **Auto-Configuration**: Seamless Prometheus integration via Juju relations
- **Dashboard Provisioning**: Deploy up to 10 dashboards via `juju config` (dashboard0-dashboard9)
- **Production Dashboard Included**: Concourse CI Build Monitor (see `dashboards/README.md`)
- **Secure Credentials**: Auto-generated passwords, retrievable via `get-admin-password` action
- **Flexible Configuration**: Customizable ports, external URLs, Grafana versions

## Quick Start

### Basic Deployment

```bash
# Deploy Grafana
juju deploy ./grafana-machine_amd64.charm grafana

# Deploy Prometheus
juju deploy prometheus-machine prometheus

# Integrate for automatic datasource configuration
juju integrate grafana:grafana-source prometheus:grafana-source

# Get admin credentials
juju run grafana/0 get-admin-password

# Access Grafana at http://<grafana-ip>:3000
juju status grafana  # Get IP address
```

### Deploy Dashboard

```bash
# Deploy the included Concourse CI Build Monitor dashboard
juju config grafana dashboard0="$(cat dashboards/concourse-ci-build-monitor.json)"

# Dashboard appears in Grafana UI within ~30 seconds
```

### Complete Observability Stack

```bash
# 1. Deploy PostgreSQL (required by Concourse)
juju deploy postgresql --channel 16/stable

# 2. Deploy Concourse CI
juju deploy concourse-ci-machine concourse --config mode=auto -n 3
juju integrate concourse postgresql

# 3. Deploy Prometheus
juju deploy prometheus-machine prometheus
juju integrate concourse:monitoring prometheus:metrics-endpoint

# 4. Deploy Grafana
juju deploy grafana-machine grafana
juju integrate grafana:grafana-source prometheus:grafana-source

# 5. Deploy dashboard
juju config grafana dashboard0="$(cat dashboards/concourse-ci-build-monitor.json)"

# 6. Get credentials
juju run grafana/0 get-admin-password
```

## Configuration

```bash
# Change HTTP port
juju config grafana http-port=8080

# Set custom admin credentials
juju config grafana admin-user=myadmin admin-password=mypassword

# Change Grafana version
juju config grafana grafana-version=11.3.0

# Set external URL (for reverse proxy)
juju config grafana external-url=https://grafana.example.com

# Provision dashboards (up to 10 slots: dashboard0-dashboard9)
juju config grafana dashboard0="$(cat my-dashboard.json)"
juju config grafana dashboard1="$(cat another-dashboard.json)"

# Remove a dashboard
juju config grafana dashboard0=""
```

## Actions

### `get-admin-password`

Retrieve admin credentials securely.

```bash
# Get credentials
juju run grafana/0 get-admin-password

# Use in scripts
PASSWORD=$(juju run grafana/0 get-admin-password --format=json | jq -r '."grafana/0".results.password')
GRAFANA_IP=$(juju status grafana --format=json | jq -r '.applications.grafana.units."grafana/0".address')
curl -u admin:$PASSWORD http://$GRAFANA_IP:3000/api/datasources
```

Password is auto-generated on first deployment, stored securely in Juju peer relation data (encrypted at rest), and shared automatically across all units.

## Dashboard Provisioning

### Basic Usage

```bash
# Provision dashboard from file
juju config grafana dashboard0="$(cat my-dashboard.json)"

# Update existing dashboard
juju config grafana dashboard0="$(cat updated-dashboard.json)"

# Remove dashboard
juju config grafana dashboard0=""
```

### Dashboard Format

Use raw Grafana dashboard JSON (not API wrapper format).

**✅ Correct:**
```json
{
  "title": "My Dashboard",
  "tags": ["monitoring"],
  "timezone": "browser",
  "panels": [...]
}
```

**❌ Incorrect** (API wrapper):
```json
{
  "dashboard": {
    "title": "My Dashboard",
    ...
  },
  "overwrite": true
}
```

### Exporting Dashboards

1. Open dashboard in Grafana UI
2. Click ⚙️ (Dashboard settings) → JSON Model
3. Copy JSON content
4. If it has a `"dashboard"` wrapper, extract: `cat exported.json | jq '.dashboard' > dashboard.json`
5. Deploy: `juju config grafana dashboard0="$(cat dashboard.json)"`

## Relations

### `grafana-source` (requires)
- **Interface**: `grafana_datasource`
- **Purpose**: Auto-configures datasources from Prometheus and other providers
- **Usage**: `juju integrate grafana:grafana-source prometheus:grafana-source`

### `grafana` (peer)
- **Interface**: `grafana_peers`
- **Purpose**: Shares admin password and configuration across units

## Architecture

### File Structure

```
/etc/grafana/grafana.ini                      # Main configuration
/etc/grafana/provisioning/datasources/        # Auto-provisioned datasources
/etc/grafana/provisioning/dashboards/         # Dashboard provisioning config
/var/lib/grafana/                             # Data directory
/var/lib/grafana/dashboards/                  # Dashboard JSON files
/var/log/grafana/                             # Logs
```

### How Datasource Provisioning Works

1. Establish relation: `juju integrate grafana:grafana-source prometheus:grafana-source`
2. Prometheus provides URL and metadata
3. Charm creates YAML in `/etc/grafana/provisioning/datasources/`
4. Grafana automatically loads the datasource (no restart needed)

Example:
```yaml
apiVersion: 1
datasources:
- name: juju_<model>_<uuid>_prometheus_<unit>
  type: prometheus
  access: proxy
  url: http://<prometheus-ip>:9090
  isDefault: true
```

### How Dashboard Provisioning Works

1. Set dashboard via config: `juju config grafana dashboard0="$(cat dashboard.json)"`
2. Charm writes file to `/var/lib/grafana/dashboards/<title>-0.json`
3. Grafana scans directory every 30 seconds and loads new dashboards
4. No service restart required

## Troubleshooting

### Grafana Won't Start

```bash
# Check service status
juju ssh grafana/0 -- systemctl status grafana-server

# Check logs
juju ssh grafana/0 -- journalctl -u grafana-server -n 50
```

### No Datasources Configured

```bash
# Check relation status
juju status --relations

# Check provisioning files
juju ssh grafana/0 -- cat /etc/grafana/provisioning/datasources/default.yaml

# Manually trigger config update
juju config grafana http-port=3000  # Set to same value
```

### Dashboards Not Appearing

```bash
# Check if dashboard files exist
juju ssh grafana/0 -- ls -la /var/lib/grafana/dashboards/

# Verify JSON is valid
cat dashboard.json | jq .

# Check Grafana logs
juju ssh grafana/0 -- journalctl -u grafana-server | grep -i dashboard

# Manually reprovision
juju config grafana dashboard0="$(cat dashboard.json)"
```

### Can't Login

```bash
# Get current password
juju run grafana/0 get-admin-password

# Reset password
juju config grafana admin-password=newpassword123
```

### Can't Access UI

```bash
# Get IP address
juju status grafana --format=json | jq -r '.applications.grafana.units."grafana/0".address'

# Check if service is listening
juju ssh grafana/0 -- sudo ss -tlnp | grep 3000

# Test from within unit
juju ssh grafana/0 -- curl -s http://localhost:3000/api/health
```

## Development

### Build

```bash
charmcraft pack
```

### Test Deployment

```bash
juju add-model grafana-test
juju deploy ./grafana-machine_amd64.charm grafana
juju status --relations
juju debug-log --include grafana
```

### Debugging

```bash
# Check configuration
juju ssh grafana/0 -- cat /etc/grafana/grafana.ini

# Check API health
juju ssh grafana/0 -- curl -s http://localhost:3000/api/health

# List datasources
PASSWORD=$(juju run grafana/0 get-admin-password --format=json | jq -r '."grafana/0".results.password')
juju ssh grafana/0 -- curl -s -u admin:$PASSWORD http://localhost:3000/api/datasources
```

## Limitations

- External database for HA not yet supported (single-unit SQLite only)
- LDAP/OAuth integration not available
- Plugin installation not automated
- Dashboard count limited to 10 (dashboard0-dashboard9)
- Alert provisioning not implemented

## Related Documentation

- [Included Dashboard Documentation](dashboards/README.md) - Concourse CI Build Monitor
- [Grafana Official Docs](https://grafana.com/docs/grafana/latest/)
- [Juju Documentation](https://juju.is/docs)

## Contributing

This charm is part of the Concourse CI observability stack. Contributions welcome!

## License

Apache 2.0
