if [[ "$VIRTUAL_ENV" = "" ]]
then
	source /opt/gravis/venv/bin/activate
fi
sudo mount -a

multitail -s 2 -cT ansi -l "./manage.py rqworker default" -cT ansi -L "./manage.py rqworker cheap" -cT ansi -L "./manage.py watcher" -l "gunicorn --log-level debug -w 4 --reload app.wsgi"
