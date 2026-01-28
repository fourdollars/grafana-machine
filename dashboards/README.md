# Grafana Dashboards

Pre-built dashboards for monitoring systems deployed via Juju.

## Concourse CI - Build Monitor

**File**: `concourse-ci-build-monitor.json`

Production-ready dashboard with 13 panels across 4 rows showing system health, build status distribution, trends, and resource usage.

### Dashboard Layout

| Row | Content |
|-----|---------|
| **1. System Health** | Web status, Active workers, Running builds, Avg duration |
| **2. Visual Analysis** | Success rate gauge, Status distribution pie chart, Last hour stats |
| **3. Build Trends** | Build rate, Starts vs Finishes, Duration over time |
| **4. System Resources** | Database connections, Worker containers, HTTP response time |

### Prerequisites

**⚠️ Requires Concourse Prometheus Exporter**

Concourse 8.0.0 doesn't expose per-job build status. Without the exporter, status panels show "0".

**Quick Setup:**
```bash
# 1. Install fly CLI on Concourse web unit
juju ssh concourse-ci-machine/0 -- "sudo wget -q -O /usr/local/bin/fly http://localhost:8080/api/v1/cli?arch=amd64\&platform=linux && sudo chmod +x /usr/local/bin/fly"

# 2. Get admin password
ADMIN_PASS=$(juju ssh concourse-ci-machine/0 -- "sudo grep CONCOURSE_ADD_LOCAL_USER /var/lib/concourse/config.env | cut -d= -f2")

# 3. Create exporter config
juju ssh concourse-ci-machine/0 -- "sudo tee /etc/concourse-exporter.env" << EOF
CONCOURSE_URL=http://localhost:8080
CONCOURSE_TEAM=main
CONCOURSE_USERNAME=admin
CONCOURSE_PASSWORD=$ADMIN_PASS
EXPORTER_PORT=9358
SCRAPE_INTERVAL=30
EOF

# 4. Deploy exporter script + systemd service (see repo for files)
# 5. Add to Prometheus config and restart
# 6. Verify: curl http://<concourse-ip>:9358/metrics | grep concourse_job_last_build_status
```

The exporter provides `concourse_job_last_build_status` metric:
- `1` = ✅ Succeeded
- `0` = ❌ Failed  
- `-1` = ⚠️ Errored
- `-2` = 🛑 Aborted
- `-3` = 🔄 Running
- `-4` = ⏸️ Pending

### Installation

**Via Juju (Recommended):**
```bash
juju config grafana dashboard0="$(cat concourse-ci-build-monitor.json)"
# Wait 30-40 seconds for provisioning
```

**Via Grafana UI:**
1. Go to `http://<grafana-ip>:3000`
2. Dashboards → Import → Upload JSON
3. Select Prometheus datasource

**Dashboard URL**: `http://<grafana-ip>:3000/d/afbi7tim93ojkf/concourse-ci-build-monitor`

### Troubleshooting

**Fresh Deployment Shows Zero Data**

Normal until you create pipelines and trigger builds. Quick test:

```bash
# Setup fly CLI
CONCOURSE_IP=$(juju status concourse-ci-machine --format=json | jq -r '.applications."concourse-ci-machine".units | to_entries[0].value.address')
wget http://$CONCOURSE_IP:8080/api/v1/cli?arch=amd64&platform=linux -O fly
chmod +x fly && sudo mv fly /usr/local/bin/

# Login (get password: juju ssh concourse-ci-machine/0 -- "sudo grep CONCOURSE_ADD_LOCAL_USER /var/lib/concourse/web-config.env")
fly -t ci login -c http://$CONCOURSE_IP:8080 -u admin -p <password>

# Create test pipeline
cat > /tmp/test.yml << 'EOF'
jobs:
  - name: success
    plan:
      - task: pass
        config:
          platform: linux
          image_resource:
            type: registry-image
            source: {repository: busybox}
          run: {path: echo, args: ["OK"]}
  - name: failure
    plan:
      - task: fail
        config:
          platform: linux
          image_resource:
            type: registry-image
            source: {repository: busybox}
          run: {path: sh, args: ["-c", "exit 1"]}
EOF

fly -t ci set-pipeline -p test -c /tmp/test.yml -n
fly -t ci unpause-pipeline -p test

# Trigger builds
fly -t ci trigger-job -j test/success
fly -t ci trigger-job -j test/failure

# Wait 60s, refresh dashboard
```

**Common Issues**

| Problem | Check |
|---------|-------|
| No data on panels | `juju status --relations \| grep prometheus` |
| Metrics not found | `curl http://<concourse-ip>:9391/metrics` |
| Dashboard not loading | `juju ssh grafana/0 -- systemctl status grafana-server` |

**Verify Prometheus Scraping:**
```bash
curl -s http://<prometheus-ip>:9090/api/v1/query?query=concourse_builds_running | jq .
```

## Creating Custom Dashboards

1. **Explore**: Grafana → Explore → `{__name__=~"concourse_.*"}`
2. **Build**: Create panels and test queries
3. **Export**: Dashboard Settings → JSON Model
4. **Clean**: Remove `id`, set `version` to 0
5. **Document**: Add section to this README

### Key Concourse Metrics

- `concourse_builds_*` - Build counters and durations
- `concourse_workers_*` - Worker registration, containers, volumes
- `concourse_db_*` - Database connections
- `concourse_http_*` - API response times

### Query Examples

```promql
# Success rate (finished builds only)
(count(concourse_job_last_build_status == 1) or vector(0)) / 
(count(concourse_job_last_build_status >= -2 and concourse_job_last_build_status <= 1) or vector(1)) * 100

# Build rate per minute
rate(concourse_builds_succeeded_total[5m]) * 60

# Average build duration
sum(rate(concourse_builds_duration_seconds_sum[5m])) / sum(rate(concourse_builds_duration_seconds_count[5m]))
```

## Contributing

When adding dashboards:

1. Use descriptive filename: `system-name-purpose.json`
2. Document in this README
3. Test all panels with real data
4. Clean JSON: Remove `id`, set `version` to 0, add panel descriptions

**Checklist:**
- [ ] Unique `uid`, descriptive `title`
- [ ] All panels have descriptions
- [ ] Queries tested and working
- [ ] Consistent colors and formatting

## Links

- [Grafana Docs](https://grafana.com/docs/grafana/latest/dashboards/)
- [PromQL Guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Concourse Metrics](https://concourse-ci.org/metrics.html)
