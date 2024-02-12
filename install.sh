#!/bin/bash
set -euo pipefail

OWNER=$USER
if [ $OWNER = "root" ]
then
  OWNER=$(logname)
  echo "Running as root, but setting $OWNER as owner."
fi

GRAVIS_BASE=/opt/gravis
GRAVIS_APP=$GRAVIS_BASE/app
DATA_PATH=$GRAVIS_BASE/data
DB_PATH=$GRAVIS_BASE/db
GRAVIS_SRC=.
VENV=$GRAVIS_BASE/venv

echo "gravis installation folder: $GRAVIS_BASE"
echo "Data folder: $DATA_PATH"
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
  if [[ ! -e $DATA_PATH ]]; then
      echo "## Creating $DATA_PATH..."
      sudo mkdir "$DATA_PATH"
      sudo mkdir "$DATA_PATH"/incoming "$DATA_PATH"/cases "$DATA_PATH"/error 
      sudo chown -R $OWNER:$OWNER $DATA_PATH
      sudo chmod a+x $DATA_PATH
  else
    echo "## $DATA_PATH already exists."
  fi
}

install_app_files() {
  if [ ! -e "$GRAVIS_APP" ]; then
    echo "## Installing app files..."
    sudo mkdir "$GRAVIS_APP"
    sudo cp -R "$GRAVIS_SRC" "$GRAVIS_APP"
    sudo cp "$GRAVIS_SRC"/install/local.install-env "$GRAVIS_APP/local.env"
    sudo chown -R $OWNER:$OWNER "$GRAVIS_APP"
  fi
}

install_packages() {
  echo "## Installing Linux packages..."
  sudo apt-get --assume-yes update
  sudo apt-get --assume-yes install -y software-properties-common build-essential sqlite3 python3.10-dev python3.10-venv postgresql nginx redis
  # sudo apt --assume-yes upgrade
}

install_dependencies() {
  echo "## Installing Python runtime environment..."
  if [ ! -e "$VENV" ]; then
    sudo mkdir "$VENV" && sudo chown $USER "$VENV"
    python3.10 -m venv "$VENV"
  fi

  echo "## Installing required Python packages..."
  sudo chown -R $OWNER:$OWNER "$GRAVIS_BASE/venv"
  sudo -u $OWNER -s <<- EOL
   set -e
   $VENV/bin/pip install --isolated wheel~=0.37.1
   $VENV/bin/pip install --isolated -r "$GRAVIS_APP/requirements.txt"
   echo -e "\nSECRET_KEY=$($VENV/bin/python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')" >> "$GRAVIS_APP/local.env"
   if [[ ! -e $GRAVIS_BASE/staticfiles ]]; then
     $VENV/bin/python $GRAVIS_APP/manage.py collectstatic
   fi
EOL
}

install_services() {
  echo "## Installing GRAVIS service..."
  cd "$GRAVIS_SRC"/install
  SYSTEMD_UNITS=(*.{service,socket})
  echo "Units to install: ${SYSTEMD_UNITS[@]}"
  sudo cp "${SYSTEMD_UNITS[@]}" /etc/systemd/system
  # gravis-gunicorn.service gravis-gunicorn.socket gravis-watcher.service gravis-worker.service gravis-worker-cheap.service gravis.service
  sudo systemctl enable "${SYSTEMD_UNITS[@]}"
  sudo systemctl daemon-reload
  sudo systemctl start gravis
  cd -
}

install_postgres() {
  echo "## Setting up postgres..."
  sudo -u postgres -s <<- EOM
    cd ~
    createuser gravis || true
    createdb gravis -O gravis || true
EOM
  echo "## Running initial migrations..."
  sudo -u $OWNER -s <<- EOK
  $VENV/bin/python $GRAVIS_APP/manage.py migrate
EOK
}

install_nginx() {
  echo "## Installing nginx..."
  sudo cp $GRAVIS_SRC/install/gravis_nginx.conf /etc/nginx/sites-available
  if [[ ! -e /etc/nginx/sites-enabled/gravis_nginx.conf ]]; then
    sudo ln -s /etc/nginx/sites-available/gravis_nginx.conf /etc/nginx/sites-enabled
  fi
  if ! sudo test -f /etc/ssl/certs/nginx-gravis-selfsigned.crt; then
    echo "Generating self-signed certificate."
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -subj "/C=US/ST=NY/L=NYC/O=GRAVIS/CN=gravis.local" -keyout /etc/ssl/private/nginx-gravis-selfsigned.key -out /etc/ssl/certs/nginx-gravis-selfsigned.crt
  else
    echo "Skipping self-signed certificate generation."
  fi

  sudo service nginx reload
}

install_docker () {
  if [ ! -x "$(command -v docker)" ]; then 
    echo "## Installing Docker..."
    sudo apt-get update
    sudo apt-get remove docker docker-engine docker.io || true
    echo '* libraries/restart-without-asking boolean true' | sudo debconf-set-selections
    sudo apt-get install apt-transport-https ca-certificates curl software-properties-common -y
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg |  sudo apt-key add -
    sudo apt-key fingerprint 0EBFCD88
    sudo add-apt-repository \
        "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) \
        stable"
    sudo apt-get update
    sudo apt-get install -y docker-ce
    # Restart docker to make sure we get the latest version of the daemon if there is an upgrade
    sudo service docker restart
    # Make sure we can actually use docker
    sudo usermod -a -G docker gravis
    sudo docker --version
  fi
}

systemd_install () {
  echo "## Performing GRAVIS installation..."
  create_user
  create_folders
  install_packages
  install_app_files
  install_dependencies
  install_postgres
  install_nginx
  install_docker
  install_services
}

systemd_install


# python_l="/usr/bin/python"
# if [ -L ${python_l} ] ; then
#    if [ ! -e ${python_l} ] ; then
#       sudo ln -s /usr/bin/python3 /usr/bin/python
#    fi
# elif [ -e ${python_l} ] ; then
#    echo "Not a link"
# else
#    sudo ln -s /usr/bin/python3 /usr/bin/python
# fi

echo "Installation complete"
