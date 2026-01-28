# Grafana Machine Charm

A Juju machine charm for deploying Grafana on bare metal, VMs, or LXD containers.

## Overview

This charm deploys Grafana, an open-source platform for monitoring and observability. It integrates seamlessly with Prometheus and other datasources through the `grafana_datasource` interface, providing a complete observability solution with automatic configuration and dashboard provisioning.

## Features

- ✅ **Machine Deployments**: Works on LXD, OpenStack, bare metal (not Kubernetes)
- ✅ **Auto-Configuration**: Seamless Prometheus integration via Juju relations
- ✅ **Config-Based Dashboard Provisioning**: Deploy dashboards via `juju config` (10 slots: dashboard0-dashboard9)
- ✅ **Included Production Dashboard**: Concourse CI Build Monitor with 21 panels (see `dashboards/`)
- ✅ **Secure Credential Management**: Auto-generated passwords with `get-admin-password` action
- ✅ **Flexible Configuration**: Customizable ports, external URLs, admin credentials
- ✅ **Multi-Unit Support**: Peer relation for password sharing across units
- ✅ **Version Management**: Configurable Grafana version (default: 11.4.0)

## Quick Start

### Deploy Grafana with Prometheus

```bash
# Deploy Grafana
juju deploy ./grafana-machine_amd64.charm grafana

# Deploy Prometheus
juju deploy prometheus-machine prometheus

# Integrate for automatic datasource configuration
juju integrate grafana:grafana-source prometheus:grafana-source

# Get admin credentials
juju run grafana/0 get-admin-password

# Access Grafana
juju status grafana  # Get IP address
# Visit http://<grafana-ip>:3000 and login with credentials from above
```

### Deploy Production Dashboard (Concourse CI)

```bash
# Deploy the included Concourse CI Build Monitor dashboard
juju config grafana dashboard0="$(cat dashboards/concourse-ci-build-monitor.json)"

# Dashboard will appear in Grafana UI within ~30 seconds
# Access via Grafana → Dashboards → "Concourse CI - Build Monitor"
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

# Provision dashboards via config (up to 10 dashboards)
juju config grafana dashboard0="$(cat my-dashboard.json)"
juju config grafana dashboard1="$(cat another-dashboard.json)"
```

## Actions

### `get-admin-password`

Retrieve the Grafana admin credentials securely.

```bash
# Get admin credentials
juju run grafana/0 get-admin-password

# Example output:
# username: admin
# password: u3Iw0FW30XIOXvQoTpZxwg
# message: Use these credentials to login to Grafana

# Use in scripts
PASSWORD=$(juju run grafana/0 get-admin-password --format=json | jq -r '.results.password')
curl -u admin:$PASSWORD http://<grafana-ip>:3000/api/datasources
```

**How it works:**
- Password is auto-generated on first deployment
- Stored securely in Juju peer relation data (encrypted at rest)
- Shared automatically across all units
- Can be overridden with `juju config grafana admin-password=...`

## Architecture

### Components

- **Grafana Server**: Runs as systemd service (`grafana-server.service`)
- **Configuration**: `/etc/grafana/grafana.ini`
- **Data Directory**: `/var/lib/grafana/`
- **Logs**: `/var/log/grafana/`
- **Datasource Provisioning**: `/etc/grafana/provisioning/datasources/`
- **Dashboard Provisioning**: `/etc/grafana/provisioning/dashboards/`
- **Dashboard Files**: `/var/lib/grafana/dashboards/`

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

## Dashboard Provisioning

The charm supports provisioning up to 10 dashboards via configuration options (`dashboard0` through `dashboard9`). This is the **recommended method** for deploying dashboards in production, as it provides version control and reproducibility.

### Included Dashboard

The charm includes a production-ready **Concourse CI Build Monitor** dashboard (`dashboards/concourse-ci-build-monitor.json`):
- 21 panels across 5 rows
- Monitors builds, workers, database, HTTP performance
- Real-time status indicators with color coding
- Grafana 11.4+ compatible

See `dashboards/README.md` for detailed documentation.

### How It Works

1. **Set Dashboard JSON**: Use `juju config` to set dashboard JSON content
2. **Auto-Provisioning**: Charm writes dashboard files to `/var/lib/grafana/dashboards/`
3. **Grafana Detection**: Grafana automatically loads dashboards (scans every 30 seconds)
4. **Updates**: Changes to dashboard config trigger automatic reprovisioning
5. **No Service Restart**: Dashboards load without restarting Grafana

### Basic Usage

```bash
# Provision the included Concourse CI dashboard
juju config grafana dashboard0="$(cat dashboards/concourse-ci-build-monitor.json)"

# Provision your own dashboard
juju config grafana dashboard1="$(cat my-custom-dashboard.json)"

# Provision multiple dashboards (up to 10 slots)
juju config grafana dashboard0="$(cat dashboard-1.json)"
juju config grafana dashboard1="$(cat dashboard-2.json)"
juju config grafana dashboard2="$(cat dashboard-3.json)"

# Update an existing dashboard
juju config grafana dashboard0="$(cat updated-dashboard.json)"

# Remove a dashboard (set to empty string)
juju config grafana dashboard0=""
```

### Dashboard JSON Format

Dashboards must be in raw Grafana dashboard JSON format (not API wrapper format).

**✅ Correct Format** (use this):
```json
{
  "title": "My Dashboard",
  "tags": ["monitoring"],
  "timezone": "browser",
  "panels": [...]
}
```

**❌ Incorrect Format** (API wrapper - don't use):
```json
{
  "dashboard": {
    "title": "My Dashboard",
    ...
  },
  "overwrite": true
}
```

### Exporting Dashboards from Grafana

1. Open dashboard in Grafana UI
2. Click ⚙️ (Dashboard settings)
3. Click "JSON Model" in left sidebar
4. Copy the JSON content
5. If it has a `"dashboard"` wrapper, extract it:
   ```bash
   cat exported.json | jq '.dashboard' > dashboard.json
   ```

### Example Workflow

```bash
# 1. Export dashboard from Grafana UI
# (Copy JSON Model content to clipboard)

# 2. Save to file
cat > my-dashboard.json << 'EOF'
{
  "title": "My Monitoring Dashboard",
  "tags": ["production", "metrics"],
  "timezone": "browser",
  "panels": [
    {
      "id": 1,
      "type": "graph",
      "title": "CPU Usage",
      "targets": [{"expr": "cpu_usage"}]
    }
  ]
}
EOF

# 3. Provision to Grafana
juju config grafana dashboard0="$(cat my-dashboard.json)"

# 4. Dashboard appears in Grafana within ~30 seconds
# Access via Grafana UI → Dashboards
```

### Dashboard Slots

The charm provides 10 dashboard slots:
- `dashboard0` through `dashboard9`
- Each slot can hold one dashboard
- Dashboards are named: `<title>-<slot>.json`
- Empty slots are ignored

### Best Practices

**✅ DO:**
- Use version control for dashboard JSON files
- Test dashboards in development before deploying to production
- Use descriptive titles and tags for organization
- Document dashboard panel queries and thresholds
- Use dashboard slots (0-9) consistently across environments

**❌ DON'T:**
- Edit dashboards only in Grafana UI (changes will be overwritten on charm upgrades)
- Store sensitive data in dashboard JSON (use variables instead)
- Create overly complex dashboards (split into multiple dashboards)
- Forget to export dashboards after UI changes

### Configuration Details

Generated provisioning configuration at `/etc/grafana/provisioning/dashboards/default.yaml`:

```yaml
apiVersion: 1
providers:
  - name: default
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

## Files and Directories

```
grafana-machine/
├── charmcraft.yaml                 # Charm build configuration
├── config.yaml                     # Configuration options schema
├── metadata.yaml                   # Charm metadata and relations
├── actions.yaml                    # Action definitions (get-admin-password)
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── dashboards/
│   ├── concourse-ci-build-monitor.json  # Production Concourse CI dashboard
│   └── README.md                   # Dashboard documentation
├── src/
│   └── charm.py                    # Main charm logic
└── lib/
    ├── grafana_installer.py        # Binary download and service setup
    ├── grafana_config.py           # Configuration and provisioning
    └── charms/
        └── grafana_k8s/v0/
            └── grafana_source.py   # Datasource relation library
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

### Complete Observability Stack (Recommended)

Deploy Grafana with Prometheus and Concourse CI for full observability:

```bash
# 1. Deploy PostgreSQL (required by Concourse)
juju deploy postgresql --channel 16/stable

# 2. Deploy Concourse CI
juju deploy concourse-ci-machine concourse --config mode=auto -n 3
juju integrate concourse postgresql

# 3. Deploy Prometheus
juju deploy prometheus-machine prometheus

# 4. Integrate Concourse → Prometheus (metrics collection)
juju integrate concourse:prometheus-scrape prometheus:metrics-endpoint

# 5. Deploy Grafana
juju deploy grafana-machine grafana

# 6. Integrate Grafana → Prometheus (datasource)
juju integrate grafana:grafana-source prometheus:grafana-source

# 7. Get Grafana credentials
juju run grafana/0 get-admin-password

# 8. Deploy Concourse CI dashboard
juju config grafana dashboard0="$(cat dashboards/concourse-ci-build-monitor.json)"

# Access:
# - Grafana: http://<grafana-ip>:3000
# - Prometheus: http://<prometheus-ip>:9090
# - Concourse: http://<concourse-ip>:8080
```

### Basic Deployment (Standalone)

```bash
juju deploy grafana-machine grafana
juju run grafana/0 get-admin-password
```

### With Prometheus Integration

```bash
juju deploy grafana-machine grafana
juju deploy prometheus-machine prometheus
juju integrate grafana:grafana-source prometheus:grafana-source
juju run grafana/0 get-admin-password
```

### Behind Reverse Proxy

```bash
juju deploy grafana-machine grafana \
  --config external-url=https://grafana.mycompany.com
# Configure your reverse proxy to forward to http://<grafana-ip>:3000
```

### High Availability (Multi-unit)

```bash
juju deploy grafana-machine grafana -n 3
# Note: Requires external database (not yet implemented)
# Admin password is automatically shared between units via peer relation
```

## Verification

After deployment, verify the observability stack:

```bash
# 1. Get admin credentials
PASSWORD=$(juju run grafana/0 get-admin-password --format=json | jq -r '."grafana/0".results.password')
GRAFANA_IP=$(juju status grafana --format=json | jq -r '.applications.grafana.units."grafana/0".address')

# 2. Check Grafana health
curl -s http://$GRAFANA_IP:3000/api/health | jq .
# Expected: {"database": "ok", "version": "11.4.0", ...}

# 3. List datasources
curl -s -u admin:$PASSWORD http://$GRAFANA_IP:3000/api/datasources | jq .
# Expected: Array with Prometheus datasource(s)

# 4. List dashboards
curl -s -u admin:$PASSWORD http://$GRAFANA_IP:3000/api/search | jq .
# Expected: Array with provisioned dashboards

# 5. Query metrics through Grafana (test datasource)
curl -s -u admin:$PASSWORD \
  "http://$GRAFANA_IP:3000/api/datasources/proxy/1/api/v1/query?query=up" | jq .
# Expected: Prometheus query results
```

## Troubleshooting

### Grafana Won't Start

```bash
# Check service status
juju ssh grafana/0 -- systemctl status grafana-server

# Check logs
juju ssh grafana/0 -- journalctl -u grafana-server -n 50 --no-pager

# Check if binary exists
juju ssh grafana/0 -- ls -la /usr/local/grafana/bin/grafana-server

# Restart service
juju ssh grafana/0 -- sudo systemctl restart grafana-server
```

### No Datasources Configured

```bash
# Check relation status
juju status --relations

# Check if Prometheus is providing data
juju show-unit prometheus/0 --format=json | jq '.["prometheus/0"]["relation-info"]'

# Check provisioning files
juju ssh grafana/0 -- cat /etc/grafana/provisioning/datasources/default.yaml

# Manually trigger config-changed hook
juju config grafana http-port=3000  # Set to same value to trigger hook
```

### Status Shows "No Datasources" After Service Restart

This is normal during service restarts. The charm uses delayed retry logic:
- Waits 3 seconds for Grafana to stabilize
- Retries up to 3 times with exponential backoff
- Status should update within 10 seconds

If status doesn't update after 30 seconds:
```bash
# Check if Grafana is actually running
juju ssh grafana/0 -- systemctl status grafana-server

# Check API is responding
juju ssh grafana/0 -- curl -s http://localhost:3000/api/health
```

### Dashboards Not Appearing

```bash
# Check if dashboard files exist
juju ssh grafana/0 -- ls -la /var/lib/grafana/dashboards/

# Check provisioning configuration
juju ssh grafana/0 -- cat /etc/grafana/provisioning/dashboards/default.yaml

# Check Grafana logs for provisioning errors
juju ssh grafana/0 -- journalctl -u grafana-server | grep -i dashboard

# Verify dashboard JSON is valid
cat dashboard.json | jq .  # Should not error

# Manually trigger reprovisioning
juju config grafana dashboard0="$(cat dashboard.json)"
```

### Can't Access Grafana UI

```bash
# Get correct IP address
juju status grafana --format=json | jq -r '.applications.grafana.units."grafana/0".address'

# Check if service is listening
juju ssh grafana/0 -- sudo ss -tlnp | grep 3000

# Get admin password
juju run grafana/0 get-admin-password

# Test from within the unit
juju ssh grafana/0 -- curl -s http://localhost:3000/api/health

# Check firewall (if applicable)
juju ssh grafana/0 -- sudo iptables -L -n | grep 3000
```

### Can't Login with Admin Credentials

```bash
# Get current admin password
juju run grafana/0 get-admin-password

# Check if password in config matches Grafana's config
juju ssh grafana/0 -- sudo grep admin_password /etc/grafana/grafana.ini

# Reset password via config
juju config grafana admin-password=newpassword123

# Wait for config-changed hook to complete
juju status --watch 2s
```

## Known Limitations

- **External Database**: HA mode requires external database (PostgreSQL/MySQL) - not yet implemented
- **Authentication**: LDAP/OAuth integration not yet supported (use built-in auth only)
- **Plugins**: Plugin installation not automated (manual installation via SSH required)
- **Backup/Restore**: No built-in backup functionality (use Juju backups or manual file backups)
- **Dashboard Count**: Limited to 10 dashboards via config (dashboard0-dashboard9)
- **Alerting**: Alert provisioning not yet implemented (configure alerts via UI)

## Roadmap

Future enhancements being considered:
- External database support for HA deployments
- LDAP/OAuth/SAML integration
- Alert rule provisioning via config
- Automated plugin installation
- Backup and restore actions
- More dashboard slots (dashboard10-dashboard99)

## Related Documentation

- **Included Dashboard**: See `dashboards/README.md` for Concourse CI Build Monitor documentation
- **Grafana Documentation**: https://grafana.com/docs/grafana/latest/
- **Juju Documentation**: https://juju.is/docs
- **Charm SDK**: https://juju.is/docs/sdk

## Contributing

This charm is part of the Concourse CI observability stack. Contributions welcome!

## License

Apache 2.0
