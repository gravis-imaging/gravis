#!/bin/bash
set -euo pipefail

install_packages() {
  echo "## Installing Linux packages..."
  sudo apt-get update
  sudo apt-get install -y software-properties-common python3-django 
  sudo apt upgrade
}

systemd_install () {
  echo "## Performing systemd-type gravis installation..."
  install_packages
}

systemd_install

echo "Installation complete"
