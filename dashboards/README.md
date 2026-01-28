# Grafana Dashboards

This directory contains pre-built Grafana dashboards for monitoring various systems.

## Concourse CI - Build Monitor Dashboard

**File**: `concourse-ci-build-monitor.json`

A comprehensive, production-ready dashboard for monitoring Concourse CI with an intuitive UI/UX design featuring color-coded panels, emoji indicators, and hierarchical information layout.

### Features

#### System Health Overview (Row 1)
- **Web Server Status** - UP/DOWN indicator with green/red background
- **Active Workers** - Real-time count of registered workers
- **Running Builds** - Currently executing builds
- **Avg Build Duration** - Average time to complete builds

#### Build Status Summary (Row 2)
- **✅ Succeeded** - Total successful builds (green background)
- **❌ Failed** - Total failed builds (red background)
- **⚠️ Errored** - Total errored builds (orange background)
- **🛑 Aborted** - Total aborted builds (yellow background)

#### Visual Analysis (Row 3)
- **Success Rate Gauge** - Percentage gauge with color thresholds (red<50%, orange<70%, yellow<90%, green≥90%)
- **Build Status Distribution** - Pie chart with percentages showing build outcome proportions
- **Build Stats (Last Hour)** - Quick view of recent build activity by status

#### Build Trends (Row 4)
- **Build Rate by Status** - Time series graph showing builds per minute for each status
- **Build Starts vs Finishes** - Comparison to detect queuing and backlog
- **Build Duration Over Time** - Historical trend of average build durations

#### System Resources (Row 5)
- **Database Connections by Pool** - PostgreSQL connections broken down by pool type (API, Backend, GC, Worker)
- **Worker Containers** - Active container and volume counts per worker
- **HTTP Response Time** - Average API response duration

### Metrics Used

**Build Metrics:**
- `concourse_builds_running` - Currently running builds
- `concourse_builds_succeeded_total` - Total successful builds
- `concourse_builds_failed_total` - Total failed builds
- `concourse_builds_errored_total` - Total errored builds
- `concourse_builds_aborted_total` - Total aborted builds
- `concourse_builds_started_total` - Total started builds
- `concourse_builds_finished_total` - Total finished builds
- `concourse_builds_duration_seconds_sum/count` - Build duration statistics

**System Metrics:**
- `up{juju_application="concourse-ci-machine"}` - Service health status
- `concourse_workers_registered` - Registered worker count
- `concourse_workers_containers` - Container count per worker
- `concourse_workers_volumes` - Volume count per worker
- `concourse_db_connections{dbname="api|backend|gc|worker"}` - Database connection pools
- `concourse_http_responses_duration_seconds_sum/count` - HTTP response time metrics

### Design Principles

- **Color Coding**: Green (success), Red (failure), Orange (error), Yellow (abort), Blue (running)
- **Emoji Indicators**: ✅ ❌ ⚠️ 🛑 for quick visual recognition
- **Hierarchical Layout**: Health → Status → Trends → Resources (top to bottom)
- **Auto-Refresh**: 30-second refresh rate for real-time monitoring
- **Consistent Theme**: Matching colors and styles across all panels

### Installation

#### Method 1: Via Charm Config-Based Provisioning (Recommended)

If you deployed the Grafana charm with config-based dashboard provisioning enabled:

```bash
# Deploy dashboard via Juju config
juju config grafana dashboard0="$(cat concourse-ci-build-monitor.json)"

# Wait 30-40 seconds for Grafana to scan the provisioning directory
# Dashboard will automatically appear in Grafana UI
```

**Advantages:**
- No manual import needed
- Dashboard survives Grafana restarts
- Managed via Juju configuration
- Easy to update or remove

#### Method 2: Via Grafana UI

1. Navigate to Grafana at `http://<grafana-ip>:3000`
2. Login with admin credentials
3. Click **Dashboards** → **Import**
4. Upload `concourse-ci-build-monitor.json`
5. Select the Prometheus datasource
6. Click **Import**

#### Method 3: Via API

```bash
GRAFANA_IP="<your-grafana-ip>"
ADMIN_PASS="<your-admin-password>"

# Prepare the API payload
jq -n --slurpfile dashboard concourse-ci-build-monitor.json \
  '{dashboard: $dashboard[0], overwrite: true}' > payload.json

# Import via API
curl -X POST \
  -H "Content-Type: application/json" \
  -u admin:$ADMIN_PASS \
  http://$GRAFANA_IP:3000/api/dashboards/db \
  -d @payload.json
```

#### Method 4: Via Juju SSH

```bash
GRAFANA_UNIT="grafana/0"
DASHBOARD_PATH="/home/ubuntu/concourse-dashboard.json"

# Copy dashboard to unit
juju scp concourse-ci-build-monitor.json $GRAFANA_UNIT:$DASHBOARD_PATH

# Import via API
juju ssh $GRAFANA_UNIT -- "bash -c '
ADMIN_PASS=\$(sudo grep admin_password /etc/grafana/grafana.ini | cut -d\" \" -f3)
jq -n --slurpfile dashboard $DASHBOARD_PATH \
  \"{dashboard: \\\$dashboard[0], overwrite: true}\" | \
curl -X POST \
  -H \"Content-Type: application/json\" \
  -u admin:\$ADMIN_PASS \
  http://localhost:3000/api/dashboards/db \
  -d @-
'"
```

### Dashboard URL

After installation, the dashboard will be available at:
```
http://<grafana-ip>:3000/d/dfbi027x9pdz4c/concourse-ci-build-monitor
```

### Configuration

The dashboard is configured to:
- **Refresh**: Every 30 seconds
- **Time Range**: Last 1 hour (adjustable)
- **Timezone**: Browser timezone
- **Panels**: 21 panels across 5 rows
- **Theme**: Works with both light and dark Grafana themes

### Customization

You can customize the dashboard by:

1. **Adjusting Time Range**: Use the time picker in the top-right corner
2. **Modifying Refresh Rate**: Click the refresh dropdown (5s, 10s, 30s, 1m, etc.)
3. **Editing Panels**: Click the panel title → Edit
4. **Changing Thresholds**: Edit panel → Field → Thresholds
5. **Adding Variables**: Dashboard Settings → Variables (e.g., filter by pipeline)
6. **Setting Up Alerts**: Panel Edit → Alert tab (requires alert notification channels)

### Troubleshooting

#### Panel Shows "No data"

**Common Causes:**
1. **Prometheus not scraping Concourse**: Check `juju status --relations` for `prometheus:scrape` relation
2. **Time range too narrow**: Expand to last 6 hours or more
3. **Concourse not generating metrics**: Trigger some builds to populate metrics
4. **Label mismatch**: This dashboard expects Juju-deployed Concourse with labels like `juju_application="concourse-ci-machine"`

**Verification Steps:**
```bash
# Check if Prometheus is scraping Concourse
curl -s http://<prometheus-ip>:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.juju_application == "concourse-ci-machine")'

# Test a specific metric
curl -s 'http://<prometheus-ip>:9090/api/v1/query?query=concourse_builds_running' | jq .
```

#### Web Server Panel Shows "No data"

This panel uses the `up` metric with Juju labels. Verify the query:
```bash
curl -s 'http://<prometheus-ip>:9090/api/v1/query?query=up{juju_application="concourse-ci-machine"}' | jq .
```

If the metric exists but panel shows no data, the label selector might need adjustment for your deployment.

#### HTTP Response Time Panel Empty

This panel requires sufficient HTTP traffic. Try:
1. Trigger several builds to generate API requests
2. Wait 5-10 minutes for rate calculations to stabilize
3. The metric `concourse_http_responses_duration_seconds_count` should be increasing

#### Database Connections Panel Shows "No data"

Verify the `concourse_db_connections` metric has the correct labels:
```bash
curl -s 'http://<prometheus-ip>:9090/api/v1/query?query=concourse_db_connections' | jq '.data.result[0].metric'
```

Expected labels: `dbname` with values `api`, `backend`, `gc`, or `worker`.

#### Metrics Not Found

If metrics are completely missing:
- Ensure Concourse is running: `juju status concourse-ci-machine`
- Check Prometheus scrape config: `juju ssh prometheus/0 -- sudo cat /etc/prometheus/prometheus.yml`
- Verify the relation: `juju status --relations | grep prometheus`
- Check Concourse metrics endpoint: `curl http://<concourse-ip>:9391/metrics`

#### Dashboard Not Loading

1. Check Grafana service: `juju ssh grafana/0 -- systemctl status grafana-server`
2. Check logs: `juju debug-log --include grafana`
3. Verify datasource connection: Grafana UI → Configuration → Data Sources
4. Test Prometheus: `curl http://<prometheus-ip>:9090/api/v1/query?query=up`

### Label Structure

This dashboard is designed for **Juju-deployed Concourse** which adds these labels to all metrics:
- `juju_application`: Application name (e.g., `concourse-ci-machine`)
- `juju_unit`: Unit name (e.g., `concourse-ci-machine/0`)
- `juju_model`: Juju model name
- `juju_model_uuid`: Model UUID
- `instance`: Instance identifier
- `job`: Prometheus job name

If your Concourse is deployed differently, you may need to adjust the label selectors in panel queries.

## Creating Custom Dashboards

To create your own dashboards:

1. **Explore Metrics**: Use Grafana's Explore feature to query Prometheus
2. **Build Panels**: Create visualizations for your metrics
3. **Test Queries**: Verify queries return data before adding to dashboard
4. **Export JSON**: Dashboard Settings → JSON Model → Copy
5. **Clean JSON**: Remove `id` field and set `version` to 0 for portability
6. **Save to Repository**: Save the JSON file in this directory
7. **Document**: Update this README with dashboard details

### Available Concourse Metrics

Run this query in Grafana Explore to see all available metrics:
```promql
{__name__=~"concourse_.*"}
```

Key metric categories:
- **Builds**: `concourse_builds_*` (running, succeeded, failed, errored, aborted, started, finished, duration)
- **Workers**: `concourse_workers_*` (registered, containers, volumes, tasks)
- **Database**: `concourse_db_*` (connections, queries, locks)
- **HTTP**: `concourse_http_*` (response times, request counts)
- **Resources**: `concourse_resource_*` (checks, gets, puts)
- **Volumes**: `concourse_volumes_*` (created, destroyed, streamed)
- **Steps**: `concourse_steps_*` (waiting, initializing, executing, succeeded, failed, errored)

### Query Best Practices

1. **Use aggregation for multi-series metrics**: `sum(metric) by (label)`
2. **Apply rate for counters**: `rate(metric_total[5m])`
3. **Use irate for volatile metrics**: `irate(metric_total[1m])`
4. **Calculate averages from histograms**: `sum(rate(metric_sum[5m])) / sum(rate(metric_count[5m]))`
5. **Add fallbacks for sparse data**: `metric or vector(0)`

## Contributing

When adding new dashboards to this directory:

1. **Use descriptive filenames**: `system-name-purpose.json` (e.g., `concourse-ci-build-monitor.json`)
2. **Update this README**: Add a section describing the dashboard features and usage
3. **Include metric descriptions**: Document all metrics used and their purpose
4. **Test thoroughly**: Verify all panels display data before committing
5. **Clean the JSON**: Remove `id` fields, set `version` to 0, use consistent formatting
6. **Use consistent naming**: Panels, rows, and variables should follow clear conventions
7. **Add descriptions**: Every panel should have a description explaining what it shows

### Dashboard JSON Checklist

Before committing a dashboard JSON file:

- [ ] `id` field removed (for portability)
- [ ] `version` set to 0 (Grafana will manage versioning)
- [ ] `uid` is unique (use lowercase alphanumeric)
- [ ] `title` is descriptive
- [ ] `tags` are relevant
- [ ] All panels have titles and descriptions
- [ ] Queries tested against real data
- [ ] Time ranges and refresh rates are sensible
- [ ] Color schemes are consistent
- [ ] Legends are clear and informative

## Related Documentation

- [Grafana Dashboard Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Concourse Metrics Documentation](https://concourse-ci.org/metrics.html)
- [Juju Prometheus Integration](https://charmhub.io/prometheus-k8s)
