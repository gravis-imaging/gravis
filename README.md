# GRAVIS Viewing Software for GRASP MRI Studies

## Installation

### Test Installation (using Vagrant)

A quick test installtion of GRAVIS can be done using Vagrant, which will provision a VM and install the software automatically into the VM.

Install both VirtualBox (https://www.virtualbox.org) and Vagrant (https://www.vagrantup.com) on your host computer. This can be done using any computer with an Intel chipset (Windows, Linux, Intel-based Apple Mac).

Clone the GRAVIS repository into a folder on your computer (e.g., C:\gravis):
```
cd 
git clone https://github.com/gravis-imaging/gravis.git C:\gravis
```

Open a command shell and type "vagrant up":
```
cd c:\gravis
vagrant up
```
This will create a new VM and install all required dependencies. Once the installation has finished, the GRAVIS Software can be accessed by opening the URL https://localhost in a modern browser (Firefox or Chrome).

### Server Installation

Automatic installation on a production server can be done using a provided installation script. GRAVIS currently requires **Ubuntu 22.04 LTS** as operation system

Check out the GRAVIS repository into your home folder on the server and start the installation:
```
cd ~
git clone https://github.com/gravis-imaging/gravis.git
cd gravis
sudo ./install.sh
```

