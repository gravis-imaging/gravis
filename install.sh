#!/bin/bash
set -euo pipefail

# sudo chown -R vagrant .

OWNER=$USER
if [ $OWNER = "root" ]
then
  OWNER=$(logname)
  echo "Running as root, but setting $OWNER as owner."
fi

GRAVIS_BASE=/opt/gravis
DATA_PATH=$GRAVIS_BASE/data
CONFIG_PATH=$GRAVIS_BASE/config
DB_PATH=$GRAVIS_BASE/db
GRAVIS_SRC=.

echo "gravis installation folder: $GRAVIS_BASE"
echo "Data folder: $DATA_PATH"
echo "Config folder: $CONFIG_PATH"
echo "Database folder: $DB_PATH"
echo "gravis source directory: $(readlink -f $GRAVIS_SRC)"
echo ""

create_user () {
  id -u gravis &>/dev/null || sudo useradd -ms /bin/bash gravis
  OWNER=gravis
}

create_folder () {
  if [[ ! -e $1 ]]; then
    echo "## Creating $1"
    sudo mkdir -p $1
    sudo chown $OWNER:$OWNER $1
    sudo chmod a+x $1
  else
    echo "## $1 already exists."
  fi
}

create_folders () {
  create_folder $GRAVIS_BASE
  create_folder $CONFIG_PATH
#   if [ $INSTALL_TYPE != "systemd" ]; then
#     create_folder $DB_PATH
#   fi

  if [[ ! -e $DATA_PATH ]]; then
      echo "## Creating $DATA_PATH..."
      sudo mkdir "$DATA_PATH"
      # sudo mkdir "$DATA_PATH"/incoming "$DATA_PATH"/studies "$DATA_PATH"/outgoing "$DATA_PATH"/success
      # sudo mkdir "$DATA_PATH"/error "$DATA_PATH"/discard "$DATA_PATH"/processing
      sudo chown -R $OWNER:$OWNER $DATA_PATH
      sudo chmod a+x $DATA_PATH
  else
    echo "## $DATA_PATH already exists."
  fi
}

install_app_files() {
  if [ ! -e "$GRAVIS_BASE"/app ]; then
    echo "## Installing app files..."
    sudo mkdir "$GRAVIS_BASE"/app
    sudo cp -R "$GRAVIS_SRC" "$GRAVIS_BASE"/app
    sudo chown -R $OWNER:$OWNER "$GRAVIS_BASE/app"
  fi
}

install_packages() {
  echo "## Installing Linux packages..."
  sudo apt-get update
  sudo apt-get install -y software-properties-common sqlite3 python3-django
  sudo apt upgrade
}

install_dependencies() {
  echo "## Installing Python runtime environment..."
  if [ ! -e "$GRAVIS_BASE/env" ]; then
    sudo mkdir "$GRAVIS_BASE/env" && sudo chown $USER "$GRAVIS_BASE/env"
    python3 -m venv "$GRAVIS_BASE/env"
  fi

  echo "## Installing required Python packages..."
  sudo chown -R $OWNER:$OWNER "$GRAVIS_BASE/env"
  echo "## Installing required Python packages 1..."
  sudo su $OWNER -c "$GRAVIS_BASE/env/bin/pip install --isolated wheel~=0.37.1"
  echo "## Installing required Python packages 2..."
  sudo su $OWNER -c "$GRAVIS_BASE/env/bin/pip install --isolated -r \"$GRAVIS_BASE/app/requirements.txt\""
  echo "## Installing required Python packages 3..."
}

systemd_install () {
  echo "## Performing systemd-type gravis installation..."
  create_user
  create_folders
  install_packages
  install_app_files
  install_dependencies
  sudo chown -R gravis:gravis "$GRAVIS_BASE"
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
