#!/bin/bash
set -euo pipefail

sudo chown -R vagrant .

install_packages() {
  echo "## Installing Linux packages..."
  sudo apt-get update
  sudo apt-get install -y software-properties-common sqlite3 python3-django 
  sudo apt upgrade
}

systemd_install () {
  echo "## Performing systemd-type gravis installation..."
  install_packages
}

systemd_install

sudo ln -s /usr/bin/python3 /usr/bin/python

echo "Installation complete"
