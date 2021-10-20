FROM python:3.9.6-alpine3.14

COPY . ./game
WORKDIR /game

RUN set -ex \
    && apk add make --no-cache --virtual .build-deps gcc python3-dev postgresql-dev musl-dev build-base \
    && apk update \
    && apk add zlib-dev libffi-dev jpeg-dev libc-dev libxml2-dev libxslt-dev \
    && python -m venv /env \
    && /env/bin/pip install --upgrade pip \
    && /env/bin/pip install --no-cache-dir -r /game/requirements.txt \
    && runDeps="$(scanelf --needed --nobanner --recursive /env \
        | awk '{ gsub(/,/, "\nso:", $2); print "so:" $2 }' \
        | sort -u \
        | xargs -r apk info --installed \
        | sort -u)" \
    && apk add --virtual rundeps $runDeps \
    && apk del .build-deps

ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH
