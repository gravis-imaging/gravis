FROM python:3.10

ADD requirements.txt ./
RUN pip install -r requirements.txt
# ADD processing.py ./
ADD processing.py ./
ADD mra.py ./
CMD ["python", "-u", "processing.py"]
