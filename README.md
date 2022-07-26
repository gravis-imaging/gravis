# Prototype for GRAVIS (GRASP Viewer)

### Installation setup

* Requires Python 3.8+
* Setup virtual Python environment (venv), as described here: https://linoxide.com/how-to-create-python-virtual-environment-on-ubuntu-20-04/
* Install Django, as described here https://docs.djangoproject.com/en/4.0/topics/install/
* Currently configured to just use SQLite as database
* Run database migration: python manage.py migrate 
* Run Django server with: python manage.py runserver
