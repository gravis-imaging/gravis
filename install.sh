#!/bin/bash
set -euo pipefail

error() {
  local parent_lineno="$1"
  local code="${3:-1}"
  echo "Error on or near line ${parent_lineno}"
  exit "${code}"
}
trap 'error ${LINENO}' ERR

OWNER=$USER
if [ $OWNER = "root" ]
then
  OWNER=$(logname)
  echo "Running as root, but setting $OWNER as owner."
fi

SECRET="${GRAVIS_SECRET:-unset}"
if [ "$SECRET" = "unset" ]
then
  SECRET=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1 || true)
fi

DB_PWD="${GRAVIS_PASSWORD:-unset}"
if [ "$DB_PWD" = "unset" ]
then
  DB_PWD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1 || true)
fi

GRAVIS_BASE=/opt/gravis
DATA_PATH=$GRAVIS_BASE/data
CONFIG_PATH=$GRAVIS_BASE/config
DB_PATH=$GRAVIS_BASE/db
GRAVIS_SRC=.

if [ -f "$CONFIG_PATH"/db.env ]; then 
  sudo chown $USER "$CONFIG_PATH"/db.env 
  source "$CONFIG_PATH"/db.env # Don't accidentally generate a new database password
  sudo chown $OWNER "$CONFIG_PATH"/db.env 
  DB_PWD=$POSTGRES_PASSWORD
fi

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
  if [ $INSTALL_TYPE != "systemd" ]; then
    create_folder $DB_PATH
  fi

  if [[ ! -e $DATA_PATH ]]; then
      echo "## Creating $DATA_PATH..."
      sudo mkdir "$DATA_PATH"
      sudo chown -R $OWNER:$OWNER $DATA_PATH
      sudo chmod a+x $DATA_PATH
  else
    echo "## $DATA_PATH already exists."
  fi
}


install_packages() {
  echo "## Installing Linux packages..."
  sudo apt-get update
  sudo apt-get install -y software-properties-common python3-django postgresql postgresql-contrib
  sudo apt upgrade
}

systemd_install () {
  echo "## Performing systemd-type gravis installation..."
  create_user
  create_folders
  install_packages
}

while getopts ":hy" opt; do
  case ${opt} in
    h )
      echo "Usage:"
      echo "    install.sh -h                     Display this help message."
      echo "    install.sh [-y] docker [OPTIONS]  Install with docker-compose."
      echo "    install.sh [-y] systemd           Install as systemd service."
      echo "    install.sh [-y] nomad             Install as nomad job."

      echo "    Options:   "
      echo "              docker:"
      echo "                      -d              Development mode "
      echo "                      -b              Build containers"
      exit 0
      ;;
    y )
      FORCE_INSTALL="y"
      ;;
    \? )
      echo "Invalid Option: -$OPTARG" 1>&2
      exit 1
      ;;
    : )
      echo "Invalid Option: -$OPTARG requires an argument" 1>&2
      exit 1
      ;;
  esac
done
shift $((OPTIND -1))
OPTIND=1
INSTALL_TYPE="${1:-docker}"
if [[ $# > 0 ]];  then shift; fi

if [ $INSTALL_TYPE = "docker" ]; then
  DOCKER_DEV=false
  DOCKER_BUILD=false
  while getopts ":db" opt; do
    case ${opt} in
      d )
        DOCKER_DEV=true
        ;;
      b )
        DOCKER_BUILD=true
        ;;
      \? )
        echo "Invalid Option for \"docker\": -$OPTARG" 1>&2
        exit 1
        ;;
    esac
  done
  shift $((OPTIND -1))
fi

if [ $FORCE_INSTALL = "y" ]; then
  echo "Forcing installation"
else
  read -p "Install with $INSTALL_TYPE (y/n)? " ANS
  if [ "$ANS" = "y" ]; then
    echo "Installing gravis..."
  else
    echo "Installation aborted."
    exit 0
  fi
fi

case "$INSTALL_TYPE" in 
  systemd )
    systemd_install
    ;;
  docker )
    docker_install
    ;;
  nomad ) 
    nomad_install
    ;;
  * )
    echo "Error: unrecognized option $INSTALL_TYPE"
    exit 1
    ;;
esac

echo "Installation complete"
