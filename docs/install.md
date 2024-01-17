# Quick start

For demo and testing purposes, Gravis is easy to run under a virtual machine using [Vagrant](). 

Check out the Gravis repository as normal, eg

```
git clone https://github.com/gravis-imaging/gravis.git
```

Create the new virtual machine and start gravis by running `vagrant up` in the repository directory. 

Once running, Gravis will be made available at `https://localhost:3333` on the host machine. You will likely have to click through a security warning, because the installation generates a self-signed certificate to serve Gravis. 

(Cornerstone3D requires "[Cross Origin Isolation](https://web.dev/articles/why-coop-coep)" as it relies on `SharedArrayBuffers`; this is all much easier to set up if Gravis always runs under HTTPS)

## Loading a test case

You can load a test case from the host machine. Create a folder in the same directory as the `Vagrantfile` called `cases`. Copy your folder of dicoms into `./cases`, so the paths look something like `./cases/case01/series001.slice001.dcm`. 

Navigate to `https://localhost:3333/filebrowser/` and navigate through `vagrant/` -> `cases/` to list the cases available. Select your case and then `Import Folder` to begin the import process.

# Server install

## Requirements
The installer is tested on Ubuntu 22.04. We expect it should mostly work on similar Linux distributions, though some manual intervention will likely be required. Requirements include python 3.10, postgresql, nginx, and redis. It is developed and tested on postgresql 12, nginx 1.18, and redis 5.0.

## Installation

Having cloned the repository, installation is a matter of running 

```
sudo ./install.sh
```

## Initial configuration

To create the initial administrator account, run the following:

```
sudo su gravis 
cd /opt/gravis
source venv/bin/activate
app/manage.py createsuperuser
```

Additionally, you will need to set the hostname that you will be accessing your server with. Add the line `PROD_HOST=<hostname>` to `local.env`, eg:

```
echo "\nPROD_HOST=host.example.com" >> /opt/gravis/app/local.env
```

## Enable local import

To enable importing cases from files available on the server, update `/opt/gravis/app/settings.py`. Find `BROWSER_BASE_DIRS` to enable browsing and importing from paths, eg:

```
BROWSER_BASE_DIRS = [{'name': 'archive1', 'location': '/media/archive1'},
                     {'name': 'archive2', 'location': '/home/gravis/archive2'}]
```

The file browser does not require any particular folder structure other than every dicom for a particular dataset should be contained in the same folder, with no subfolders. 

