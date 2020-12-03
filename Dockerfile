FROM python:3.8.6-buster
COPY . /src
RUN pip install -r /src/requirements.txt
