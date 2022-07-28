install_packages() {
  echo "## Installing Linux packages..."
  sudo apt-get update
  sudo apt-get install -y build-essential wget git dcmtk jq inetutils-ping sshpass postgresql postgresql-contrib libpq-dev git-lfs python3-wheel python3.8-dev python3.8 python3.8-ven
}

systemd_install () {
  echo "## Performing systemd-type gravis installation..."
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
Footer
