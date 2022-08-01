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

python_l="/usr/bin/python"
if [ -L ${python_l} ] ; then
   if [ ! -e ${python_l} ] ; then
      sudo ln -s /usr/bin/python3 /usr/bin/python
   fi
elif [ -e ${python_l} ] ; then
   echo "Not a link"
else
   sudo ln -s /usr/bin/python3 /usr/bin/python
fi

echo "Installation complete"
