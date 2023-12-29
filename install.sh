#!/bin/bash
set -euo pipefail

OWNER=$USER
if [ $OWNER = "root" ]
then
  OWNER=$(logname)
  echo "Running as root, but setting $OWNER as owner."
fi

GRAVIS_BASE=/opt/gravis
DATA_PATH=$GRAVIS_BASE/data
DB_PATH=$GRAVIS_BASE/db
GRAVIS_SRC=.

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
#   if [ $INSTALL_TYPE != "systemd" ]; then
#     create_folder $DB_PATH
#   fi

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
  if [ ! -e "$GRAVIS_BASE"/app ]; then
    echo "## Installing app files..."
    sudo mkdir "$GRAVIS_BASE"/app
    sudo cp -R "$GRAVIS_SRC" "$GRAVIS_BASE"/app
    sudo chown -R $OWNER:$OWNER "$GRAVIS_BASE/app"
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
  if [ ! -e "$GRAVIS_BASE/venv" ]; then
    sudo mkdir "$GRAVIS_BASE/venv" && sudo chown $USER "$GRAVIS_BASE/venv"
    python3.10 -m venv "$GRAVIS_BASE/venv"
  fi

  echo "## Installing required Python packages..."
  sudo chown -R $OWNER:$OWNER "$GRAVIS_BASE/venv"
  sudo su $OWNER -c "$GRAVIS_BASE/venv/bin/pip install --isolated wheel~=0.37.1"
  sudo su $OWNER -c "$GRAVIS_BASE/venv/bin/pip install --isolated -r \"$GRAVIS_BASE/app/requirements.txt\""
}

install_services() {
   echo "## Installing services..."
  sudo cp "$GRAVIS_SRC"/install/*.{service,socket} /etc/systemd/system
  sudo systemctl enable gravis-gunicorn.service gravis-gunicorn.socket gravis-watcher.service gravis-worker.service gravis-worker-cheap.service gravis.service
  sudo systemctl start gravis
}

install_postgres() {
  echo "## Setting up postgres..."
  sudo -u postgres -s <<- EOM
    cd ~
    createuser gravis || true
    createdb gravis -O gravis || true
EOM
  echo "## Running initial migrations..."
  sudo -u gravis -s <<- EOK
  cd $GRAVIS_BASE/app
  ../venv/bin/python manage.py migrate
EOK
}

install_nginx() {
  echo "## Nginx"
  sudo cp $GRAVIS_SRC/install/gravis_nginx.conf /etc/nginx/sites-available
  sudo ln -s /etc/nginx/sites-available/gravis_nginx.conf /etc/nginx/sites-enabled
  sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -subj "/C=US/ST=NY/L=NYC/O=GRAVIS/CN=gravis.local" -keyout /etc/ssl/private/nginx-selfsigned.key -out /etc/ssl/certs/nginx-selfsigned.crt
  sudo service nginx reload
}

systemd_install () {
  echo "## Performing systemd-type gravis installation..."
  create_user
  create_folders
  install_packages
  install_app_files
  install_dependencies
  install_postgres
  install_nginx
  sudo chown -R $OWNER:$OWNER "$GRAVIS_BASE"
}

systemd_install

# sudo chown -R vagrant .
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
