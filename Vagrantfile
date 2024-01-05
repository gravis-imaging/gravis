# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.
Vagrant.configure("2") do |config|
    # The most common configuration options are documented and commented below.
    # For a complete reference, please see the online documentation at
    # https://docs.vagrantup.com.
  
    # Every Vagrant development environment requires a box. You can search for
    # boxes at https://vagrantcloud.com/search.
    config.vm.box = "ubuntu/jammy64"
  
    # Disable automatic box update checking. If you disable this, then
    # boxes will only be checked for updates when the user runs
    # `vagrant box outdated`. This is not recommended.
    # config.vm.box_check_update = false
  
    # Create a forwarded port mapping which allows access to a specific port
    # within the machine from a port on the host machine. In the example below,
    # accessing "localhost:8080" will access port 80 on the guest machine.
    # NOTE: This will enable public access to the opened port
    # config.vm.network "forwarded_port", guest: 80, host: 8080
  
    # Create a forwarded port mapping which allows access to a specific port
    # within the machine from a port on the host machine and only allow access
    # via 127.0.0.1 to disable public access
    config.vm.network "forwarded_port", guest: 443, host: 3333, host_ip: "127.0.0.1", auto_correct: false
    config.vm.network "forwarded_port", guest: 22, host: 2545, auto_correct: false, host_ip: "127.0.0.1", id: "ssh"
  
    # config.vm.hostname = "gravis.local"
  
    # Create a private network, which allows host-only access to the machine
    # using a specific IP.
    # config.vm.network "private_network", ip: "192.168.33.20"
  
    # Create a public network, which generally matched to bridged network.
    # Bridged networks make the machine appear as another physical device on
    # your network.
    
    # config.vm.network "public_network"
  
    # Share an additional folder to the guest VM. The first argument is
    # the path on the host to the actual folder. The second argument is
    # the path on the guest to mount the folder. And the optional third
    # argument is a set of non-required options.
    # config.vm.synced_folder "../data", "/vagrant_data"
    config.vm.synced_folder ".", "/vagrant"
  
    # Provider-specific configuration so you can fine-tune various
    # backing providers for Vagrant. These expose provider-specific options.
    # Example for VirtualBox:
    #
    config.vm.provider "virtualbox" do |vb|
    #  vb.customize ["setextradata", :id, "VBoxInternal2/SharedFoldersEnableSymlinksCreate/v-root", "1"]
    #   # Display the VirtualBox GUI when booting the machine
       vb.gui = true
       vb.customize [ "modifyvm", :id, "--uart1", "0x3F8", "4" ]
      # Create a NULL serial port to skip console logging by default
       vb.customize [ "modifyvm", :id, "--uartmode1", "file", File::NULL ]
       # config.vm.network "private_network", ip: "192.168.50.4", virtualbox__intnet: "mynetwork"
      # Customize the amount of memory on the VM:
       vb.memory = "5120"
       vb.cpus = 2
    end
    #
    # View the documentation for the provider you are using for more
    # information on available options.
  
    # Enable provisioning with a shell script. Additional provisioners such as
    # Ansible, Chef, Docker, Puppet and Salt are also available. Please see the
    # documentation for more information about their specific syntax and use.
    config.vm.provision "shell", inline: <<-SHELL
    cp -r /vagrant/gravis /home/vagrant/ && cd gravis
    sudo ./install.sh
    echo "\nPROD_HOST=localhost:3333" >> /opt/gravis/app/local.env
    sudo systemctl restart gravis-gunicorn
    sudo -u gravis -s <<- EOK
       DJANGO_SUPERUSER_PASSWORD=gravis /opt/gravis/venv/bin/python /opt/gravis/app/manage.py createsuperuser --noinput --username admin --email=admin@localhost
EOK
    echo "Default user/password: admin / gravis"
  
SHELL
end
  