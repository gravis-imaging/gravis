# Prototype for GRAVIS (GRASP Viewer)

### Installation setup

* Requires Python 3.8+
* Checkout repo into folder gravis
* Setup virtual Python environment (venv) in gravis/env, as described here: https://linoxide.com/how-to-create-python-virtual-environment-on-ubuntu-20-04/
* Install Django, as described here https://docs.djangoproject.com/en/4.0/topics/install/
* App is currently configured to just use SQLite as database
* Run database migration in gravis/app: python manage.py migrate 
* Run Django server in gravis/app with: python manage.py runserver
