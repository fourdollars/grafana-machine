#!/usr/bin/env python3
"""
Grafana Configuration Library - Handles grafana.ini, datasource, and dashboard provisioning
"""

import logging
import yaml
import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

GRAFANA_CONFIG_DIR = "/etc/grafana"
GRAFANA_CONFIG_FILE = f"{GRAFANA_CONFIG_DIR}/grafana.ini"
GRAFANA_DATA_DIR = "/var/lib/grafana"
GRAFANA_LOGS_DIR = "/var/log/grafana"
GRAFANA_PROVISIONING_DIR = f"{GRAFANA_CONFIG_DIR}/provisioning"
GRAFANA_DASHBOARDS_DIR = f"{GRAFANA_DATA_DIR}/dashboards"


class GrafanaConfig:
    """Handle Grafana configuration file generation"""

    def __init__(self, charm):
        self.charm = charm
        self.config = charm.config

    def generate_config(self, admin_password: str):
        """Generate grafana.ini configuration file

        Args:
            admin_password: Admin password to set in config
        """
        logger.info("Generating Grafana configuration")

        http_port = self.config.get("http-port", 3000)
        admin_user = self.config.get("admin-user", "admin")
        log_level = self.config.get("log-level", "info")
        enable_anonymous = self.config.get("enable-anonymous", False)
        allow_embedding = self.config.get("allow-embedding", False)

        # Get external URL or construct from unit IP
        external_url = self.config.get("external-url", "")
        if not external_url:
            try:
                # Try to get unit IP
                unit_ip = self.charm.model.get_binding("juju-info").network.bind_address
                external_url = f"http://{unit_ip}:{http_port}"
            except Exception as e:
                logger.warning(f"Could not determine unit IP: {e}")
                external_url = f"http://localhost:{http_port}"

        config_content = f"""[paths]
data = {GRAFANA_DATA_DIR}
logs = {GRAFANA_LOGS_DIR}
plugins = {GRAFANA_DATA_DIR}/plugins
provisioning = {GRAFANA_PROVISIONING_DIR}

[server]
http_port = {http_port}
root_url = {external_url}
enable_gzip = true

[security]
admin_user = {admin_user}
admin_password = {admin_password}
allow_embedding = {str(allow_embedding).lower()}

[auth.anonymous]
enabled = {str(enable_anonymous).lower()}
org_role = Viewer

[log]
mode = console file
level = {log_level}

[log.console]
level = {log_level}

[log.file]
level = {log_level}
log_rotate = true
max_lines = 1000000
max_size_shift = 28
daily_rotate = true
max_days = 7

[analytics]
reporting_enabled = false
check_for_updates = false

[snapshots]
external_enabled = false
"""

        config_path = Path(GRAFANA_CONFIG_FILE)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_content)

        logger.info(f"Configuration written to {GRAFANA_CONFIG_FILE}")

    def provision_datasources(self, datasources: List[Dict[str, Any]]):
        """Provision datasources from relations

        Args:
            datasources: List of datasource configurations from relations
        """
        if not datasources:
            logger.info("No datasources to provision")
            return

        logger.info(f"Provisioning {len(datasources)} datasources")

        # Create datasource provisioning configuration
        provisioning_config = {
            "apiVersion": 1,
            "datasources": datasources,
        }

        # Write provisioning file
        datasources_path = Path(f"{GRAFANA_PROVISIONING_DIR}/datasources/default.yaml")
        datasources_path.parent.mkdir(parents=True, exist_ok=True)

        with datasources_path.open("w") as f:
            yaml.dump(provisioning_config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Datasources provisioned to {datasources_path}")

    def build_datasource_config(
        self,
        name: str,
        source_type: str,
        url: str,
        is_default: bool = True,
        access: str = "proxy",
        uid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a datasource configuration dictionary

        Args:
            name: Datasource name
            source_type: Type of datasource (e.g., 'prometheus', 'loki')
            url: URL of the datasource
            is_default: Whether this is the default datasource
            access: Access mode ('proxy' or 'direct')
            uid: Unique identifier for the datasource

        Returns:
            Datasource configuration dictionary
        """
        config = {
            "name": name,
            "type": source_type,
            "access": access,
            "url": url,
            "isDefault": is_default,
            "editable": True,
        }

        if uid:
            config["uid"] = uid

        return config

    def provision_dashboards(self):
        """Provision dashboards from config options (dashboard0-dashboard9)"""
        dashboards = []
        dashboard_dir = Path(GRAFANA_DASHBOARDS_DIR)
        dashboard_dir.mkdir(parents=True, exist_ok=True)

        expected_files = set()

        for i in range(10):
            dashboard_key = f"dashboard{i}"
            dashboard_json = self.config.get(dashboard_key, "")

            if not dashboard_json or not dashboard_json.strip():
                for existing_file in dashboard_dir.glob(f"*-{i}.json"):
                    logger.info(
                        f"Removing dashboard file for empty slot {i}: {existing_file.name}"
                    )
                    existing_file.unlink()
                continue

            try:
                dashboard_data = json.loads(dashboard_json)

                dashboard_title = dashboard_data.get("title", f"Dashboard {i}")
                safe_filename = (
                    dashboard_title.lower().replace(" ", "-").replace("/", "-")
                )
                dashboard_file = dashboard_dir / f"{safe_filename}-{i}.json"

                dashboard_file.write_text(json.dumps(dashboard_data, indent=2))

                import pwd
                import grp

                grafana_uid = pwd.getpwnam("grafana").pw_uid
                grafana_gid = grp.getgrnam("grafana").gr_gid
                os.chown(dashboard_file, grafana_uid, grafana_gid)

                expected_files.add(dashboard_file.name)
                dashboards.append(dashboard_title)
                logger.info(f"Provisioned dashboard: {dashboard_title} (slot {i})")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {dashboard_key}: {e}")
            except Exception as e:
                logger.error(f"Failed to provision {dashboard_key}: {e}")

        if dashboards:
            provisioning_config = {
                "apiVersion": 1,
                "providers": [
                    {
                        "name": "default",
                        "orgId": 1,
                        "folder": "",
                        "type": "file",
                        "disableDeletion": False,
                        "updateIntervalSeconds": 30,
                        "allowUiUpdates": True,
                        "options": {
                            "path": str(dashboard_dir),
                            "foldersFromFilesStructure": False,
                        },
                    }
                ],
            }

            dashboards_config_path = Path(
                f"{GRAFANA_PROVISIONING_DIR}/dashboards/default.yaml"
            )
            dashboards_config_path.parent.mkdir(parents=True, exist_ok=True)

            with dashboards_config_path.open("w") as f:
                yaml.dump(
                    provisioning_config, f, default_flow_style=False, sort_keys=False
                )

            logger.info(
                f"Dashboard provisioning configured: {len(dashboards)} dashboard(s)"
            )
        else:
            logger.info("No dashboards configured")
