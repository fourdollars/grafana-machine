#!/usr/bin/env python3
"""
Grafana Installer Library - Handles downloading and installing Grafana
"""

import logging
import os
import pwd
import grp
import subprocess
import tarfile
import tempfile
import secrets
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Installation paths
GRAFANA_USER = "grafana"
GRAFANA_GROUP = "grafana"
GRAFANA_INSTALL_DIR = "/usr/local/grafana"
GRAFANA_DATA_DIR = "/var/lib/grafana"
GRAFANA_CONFIG_DIR = "/etc/grafana"
GRAFANA_CONFIG_FILE = f"{GRAFANA_CONFIG_DIR}/grafana.ini"
GRAFANA_LOGS_DIR = "/var/log/grafana"
GRAFANA_PLUGINS_DIR = f"{GRAFANA_DATA_DIR}/plugins"
GRAFANA_PROVISIONING_DIR = f"{GRAFANA_CONFIG_DIR}/provisioning"
GRAFANA_DASHBOARDS_DIR = f"{GRAFANA_DATA_DIR}/dashboards"


class GrafanaInstaller:
    """Handle Grafana installation and lifecycle"""

    def __init__(self, charm):
        self.charm = charm
        self.unit = charm.unit
        self.config = charm.config

    def setup_user_and_directories(self):
        """Create grafana user and required directories"""
        logger.info("Creating grafana user and directories")

        # Create grafana group if it doesn't exist
        try:
            grp.getgrnam(GRAFANA_GROUP)
        except KeyError:
            subprocess.run(
                ["groupadd", "--system", GRAFANA_GROUP],
                check=True,
                capture_output=True,
            )
            logger.info(f"Created group {GRAFANA_GROUP}")

        # Create grafana user if it doesn't exist
        try:
            pwd.getpwnam(GRAFANA_USER)
        except KeyError:
            subprocess.run(
                [
                    "useradd",
                    "--system",
                    "--gid",
                    GRAFANA_GROUP,
                    "--no-create-home",
                    "--shell",
                    "/bin/false",
                    GRAFANA_USER,
                ],
                check=True,
                capture_output=True,
            )
            logger.info(f"Created user {GRAFANA_USER}")

        # Create directories
        directories = [
            GRAFANA_INSTALL_DIR,
            GRAFANA_DATA_DIR,
            GRAFANA_CONFIG_DIR,
            GRAFANA_LOGS_DIR,
            GRAFANA_PLUGINS_DIR,
            GRAFANA_DASHBOARDS_DIR,
            f"{GRAFANA_PROVISIONING_DIR}/datasources",
            f"{GRAFANA_PROVISIONING_DIR}/dashboards",
            f"{GRAFANA_PROVISIONING_DIR}/notifiers",
            f"{GRAFANA_PROVISIONING_DIR}/plugins",
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            os.chown(
                directory,
                pwd.getpwnam(GRAFANA_USER).pw_uid,
                grp.getgrnam(GRAFANA_GROUP).gr_gid,
            )
            logger.info(f"Created directory {directory}")

    def install_grafana(self, version: str):
        """Download and install Grafana binary"""
        logger.info(f"Installing Grafana version {version}")

        # Construct download URL
        arch = self._get_architecture()
        url = (
            f"https://dl.grafana.com/oss/release/grafana-{version}.linux-{arch}.tar.gz"
        )

        logger.info(f"Downloading from {url}")

        # Download to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp_file:
            tmp_path = tmp_file.name
            subprocess.run(
                ["curl", "-L", "-o", tmp_path, url],
                check=True,
                capture_output=True,
            )

        try:
            # Extract tarball
            logger.info(f"Extracting Grafana tarball")
            with tarfile.open(tmp_path, "r:gz") as tar:
                tar.extractall(path="/tmp")

            # Move extracted directory to install location
            extracted_dir = f"/tmp/grafana-v{version}"

            # Remove old installation if exists
            if Path(GRAFANA_INSTALL_DIR).exists():
                subprocess.run(["rm", "-rf", GRAFANA_INSTALL_DIR], check=True)

            # Move to install directory
            subprocess.run(
                ["mv", extracted_dir, GRAFANA_INSTALL_DIR],
                check=True,
            )

            # Make binaries executable
            bin_path = f"{GRAFANA_INSTALL_DIR}/bin/grafana-server"
            cli_path = f"{GRAFANA_INSTALL_DIR}/bin/grafana-cli"
            os.chmod(bin_path, 0o755)
            os.chmod(cli_path, 0o755)

            # Set ownership
            subprocess.run(
                ["chown", "-R", f"{GRAFANA_USER}:{GRAFANA_GROUP}", GRAFANA_INSTALL_DIR],
                check=True,
            )

            logger.info(f"Grafana {version} installed successfully")

        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def create_systemd_service(self):
        """Create systemd service file for Grafana"""
        logger.info("Creating Grafana systemd service")

        service_content = f"""[Unit]
Description=Grafana
Documentation=https://grafana.com/docs/
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User={GRAFANA_USER}
Group={GRAFANA_GROUP}
WorkingDirectory={GRAFANA_INSTALL_DIR}
ExecStart={GRAFANA_INSTALL_DIR}/bin/grafana-server \\
    --config={GRAFANA_CONFIG_FILE} \\
    --homepath={GRAFANA_INSTALL_DIR}

Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
"""

        service_path = Path("/etc/systemd/system/grafana-server.service")
        service_path.write_text(service_content)
        os.chmod(service_path, 0o644)

        # Reload systemd
        subprocess.run(["systemctl", "daemon-reload"], check=True)

        logger.info("Systemd service created")

    def start_service(self):
        """Start Grafana service"""
        logger.info("Starting Grafana service")
        subprocess.run(["systemctl", "enable", "grafana-server"], check=True)
        subprocess.run(["systemctl", "start", "grafana-server"], check=True)

    def stop_service(self):
        """Stop Grafana service"""
        logger.info("Stopping Grafana service")
        subprocess.run(["systemctl", "stop", "grafana-server"], check=True)

    def restart_service(self):
        """Restart Grafana service"""
        logger.info("Restarting Grafana service")
        subprocess.run(["systemctl", "restart", "grafana-server"], check=True)

    def is_service_running(self) -> bool:
        """Check if Grafana service is running"""
        result = subprocess.run(
            ["systemctl", "is-active", "grafana-server"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def is_installed(self) -> bool:
        """Check if Grafana is installed"""
        return Path(f"{GRAFANA_INSTALL_DIR}/bin/grafana-server").exists()

    def generate_admin_password(self) -> str:
        """Generate a secure random admin password"""
        return secrets.token_urlsafe(16)

    def _get_architecture(self) -> str:
        """Get system architecture for download"""
        arch = os.uname().machine
        if arch == "x86_64":
            return "amd64"
        elif arch == "aarch64":
            return "arm64"
        else:
            raise RuntimeError(f"Unsupported architecture: {arch}")
