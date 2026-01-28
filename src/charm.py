#!/usr/bin/env python3
"""
Grafana Machine Charm - Deploy Grafana on machines/VMs
Consumes datasources from Prometheus via grafana_datasource interface
"""

import logging
import sys
import requests
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from ops.charm import CharmBase, RelationChangedEvent
from ops.main import main
from ops.model import (
    ActiveStatus,
    WaitingStatus,
    BlockedStatus,
    MaintenanceStatus,
)

# Import grafana source library
try:
    from charms.grafana_k8s.v0.grafana_source import GrafanaSourceConsumer

    HAS_GRAFANA_SOURCE = True
except ImportError:
    HAS_GRAFANA_SOURCE = False

# Import helper modules
try:
    from grafana_installer import GrafanaInstaller
    from grafana_config import GrafanaConfig

    HAS_HELPERS = True
except ImportError:
    HAS_HELPERS = False

# Configure logging
log_handlers = [logging.StreamHandler()]
log_file_path = Path("/var/log/grafana.log")
if log_file_path.parent.exists() and log_file_path.parent.is_dir():
    try:
        log_handlers.append(logging.FileHandler(log_file_path))
    except (PermissionError, OSError):
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger("grafana-machine")

# Peer relation data keys
PEER_ADMIN_PASSWORD_KEY = "admin_password"


class GrafanaMachineCharm(CharmBase):
    """Main Grafana Machine Charm class"""

    def __init__(self, *args):
        super().__init__(*args)

        # Check for required libraries
        if not HAS_GRAFANA_SOURCE:
            logger.error("grafana_source library not available")
            self.unit.status = BlockedStatus("Missing grafana_source library")
            return

        if not HAS_HELPERS:
            logger.error("Helper modules not available")
            self.unit.status = BlockedStatus("Missing helper modules")
            return

        # Initialize helpers
        self.installer = GrafanaInstaller(self)
        self.config_manager = GrafanaConfig(self)

        # Initialize GrafanaSourceConsumer
        # Generate a unique grafana UID based on model UUID
        grafana_uid = f"grafana-{self.model.uuid[:8]}"

        # Get external URL for Grafana
        http_port = self.config.get("http-port", 3000)
        external_url = self.config.get("external-url", "")
        if not external_url:
            try:
                unit_ip = self.model.get_binding("juju-info").network.bind_address
                external_url = f"http://{unit_ip}:{http_port}"
            except Exception:
                external_url = f"http://localhost:{http_port}"

        self.grafana_source_consumer = GrafanaSourceConsumer(
            self,
            grafana_uid=grafana_uid,
            grafana_base_url=external_url,
            relation_name="grafana-source",
        )

        # Register event handlers
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.stop, self._on_stop)

        # Grafana source relation events
        self.framework.observe(
            self.on.grafana_source_relation_changed,
            self._on_grafana_source_changed,
        )

        # Peer relation for sharing admin password
        self.framework.observe(
            self.on["grafana"].relation_created,
            self._on_peer_relation_created,
        )

    @property
    def peers(self):
        """Return the peer relation for use by GrafanaSourceConsumer."""
        return self.model.get_relation("grafana")

    def _on_install(self, event):
        """Install Grafana during the install hook"""
        logger.info("Running install hook")
        self.unit.status = MaintenanceStatus("Installing Grafana")

        try:
            # Create grafana user and directories
            self.installer.setup_user_and_directories()

            # Download and install Grafana binary
            version = self.config.get("grafana-version", "11.4.0")
            self.installer.install_grafana(version)

            # Get or generate admin password
            admin_password = self._get_or_generate_admin_password()

            # Generate initial configuration
            self.config_manager.generate_config(admin_password)

            # Provision dashboards from config
            self.config_manager.provision_dashboards()

            # Create systemd service
            self.installer.create_systemd_service()

            logger.info("Grafana installation completed")
            self.unit.status = MaintenanceStatus("Grafana installed")

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            self.unit.status = BlockedStatus(f"Installation failed: {e}")
            raise

    def _on_config_changed(self, event):
        """Handle configuration changes"""
        logger.info("Configuration changed")

        try:
            # Get or generate admin password
            admin_password = self._get_or_generate_admin_password()

            # Regenerate configuration with new settings
            self.config_manager.generate_config(admin_password)

            # Update datasource provisioning
            self._provision_datasources()

            # Update dashboard provisioning
            self.config_manager.provision_dashboards()

            # Restart service to apply changes
            if self.installer.is_service_running():
                self.installer.restart_service()
                logger.info("Grafana restarted with new configuration")

            self._update_status()

        except Exception as e:
            logger.error(f"Configuration update failed: {e}")
            self.unit.status = BlockedStatus(f"Configuration failed: {e}")

    def _on_start(self, event):
        """Start Grafana service"""
        logger.info("Starting Grafana")

        try:
            self.installer.start_service()
            self._update_status()
        except Exception as e:
            logger.error(f"Failed to start Grafana: {e}")
            self.unit.status = BlockedStatus(f"Failed to start: {e}")

    def _on_update_status(self, event):
        """Periodic status check"""
        self._update_status()

    def _on_stop(self, event):
        """Stop Grafana service"""
        logger.info("Stopping Grafana")
        try:
            self.installer.stop_service()
        except Exception as e:
            logger.error(f"Failed to stop Grafana: {e}")

    def _on_grafana_source_changed(self, event: RelationChangedEvent):
        """Handle changes to grafana-source relations"""
        logger.info("Grafana source relation changed")

        try:
            # Provision datasources from relations
            self._provision_datasources()

            # Restart service to reload provisioning
            if self.installer.is_service_running():
                self.installer.restart_service()
                logger.info("Grafana restarted with new datasources")

            self._update_status()

        except Exception as e:
            logger.error(f"Failed to update datasources: {e}")
            self.unit.status = BlockedStatus(f"Datasource update failed: {e}")

    def _on_peer_relation_created(self, event):
        """Handle peer relation creation for sharing admin password"""
        logger.info("Peer relation created")
        # Ensure admin password is generated and shared
        self._get_or_generate_admin_password()

    def _get_or_generate_admin_password(self) -> str:
        """Get admin password from config, peer data, or generate new one"""
        # First check config
        config_password = self.config.get("admin-password", "")
        if config_password:
            logger.info("Using admin password from config")
            return config_password

        # Check peer relation data
        peer_relation = self.model.get_relation("grafana")
        if peer_relation and self.unit.is_leader():
            # Leader stores password in peer data
            password = peer_relation.data[self.app].get(PEER_ADMIN_PASSWORD_KEY)
            if not password:
                password = self.installer.generate_admin_password()
                peer_relation.data[self.app][PEER_ADMIN_PASSWORD_KEY] = password
                logger.info("Generated and stored new admin password in peer data")
            return password
        elif peer_relation:
            # Non-leader reads from peer data
            password = peer_relation.data[self.app].get(PEER_ADMIN_PASSWORD_KEY)
            if password:
                return password

        # Fallback: generate temporary password
        # This should only happen during initial install before peer relation is established
        logger.warning(
            "No admin password in config or peer data, using temporary password"
        )
        return "admin"  # Grafana's default

    def _provision_datasources(self):
        """Provision datasources from grafana-source relations"""
        datasources = []

        # Get datasources from GrafanaSourceConsumer
        try:
            # The grafana_source library provides sources via the consumer
            for source in self.grafana_source_consumer.sources:
                logger.info(f"Processing datasource: {source}")

                # Build datasource config
                datasource_config = self.config_manager.build_datasource_config(
                    name=source.get("source_name", "Prometheus"),
                    source_type=source.get("source_type", "prometheus"),
                    url=source.get("url", ""),
                    is_default=True,
                    access="proxy",
                    uid=source.get("uid", None),
                )
                datasources.append(datasource_config)

        except Exception as e:
            logger.warning(f"Failed to get datasources from consumer: {e}")

        # Provision datasources
        self.config_manager.provision_datasources(datasources)

        if datasources:
            logger.info(f"Provisioned {len(datasources)} datasources")
        else:
            logger.info("No datasources to provision")

    def _get_datasource_count_from_api(self) -> int:
        """Query Grafana API to get actual datasource count"""
        try:
            http_port = self.config.get("http-port", 3000)
            admin_user = self.config.get("admin-user", "admin")
            admin_password = self._get_or_generate_admin_password()

            # Query datasources API
            response = requests.get(
                f"http://localhost:{http_port}/api/datasources",
                auth=(admin_user, admin_password),
                timeout=5,
            )

            if response.status_code == 200:
                datasources = response.json()
                return len(datasources)

        except Exception as e:
            logger.debug(f"Failed to query Grafana API: {e}")

        return 0

    def _update_status(self):
        """Update unit status based on current state"""
        if not self.installer.is_installed():
            self.unit.status = BlockedStatus("Grafana not installed")
            return

        if not self.installer.is_service_running():
            self.unit.status = BlockedStatus("Grafana service not running")
            return

        # Get datasource count from API
        datasource_count = self._get_datasource_count_from_api()

        # Get external URL
        http_port = self.config.get("http-port", 3000)
        external_url = self.config.get("external-url", "")
        if not external_url:
            try:
                unit_ip = self.model.get_binding("juju-info").network.bind_address
                external_url = f"http://{unit_ip}:{http_port}"
            except Exception:
                external_url = f"http://localhost:{http_port}"

        if datasource_count == 0:
            self.unit.status = ActiveStatus(
                f"Grafana ready (no datasources) - {external_url}"
            )
        else:
            self.unit.status = ActiveStatus(
                f"Grafana ready ({datasource_count} datasources) - {external_url}"
            )


if __name__ == "__main__":
    main(GrafanaMachineCharm)
