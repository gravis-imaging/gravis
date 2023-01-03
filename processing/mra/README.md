# processing

## build docker image

```bash 
./build.sh
```

## push  docker image

```bash
docker push gravis-processing
```

## run docker container

```bash
./run.sh
```

## clear all rq jobs
```
from redis import Redis
from rq import Queue

queues = (
    Queue('default', connection=Redis()),
    Queue('failed', connection=Redis()),
)

for q in queues:
    q.empty() 
```

## check status of rq
```
rqinfo
```

## run rq worker
```
python manage.py rqworker default
```

## run django server 
```
python manage.py runserver
```