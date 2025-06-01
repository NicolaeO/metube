#!/usr/bin/env python3
# pylint: disable=no-member,method-hidden

import os
import sys
import logging
import socketio
import json
import pathlib
import dotenv

from ytdl import DownloadQueueNotifier, DownloadQueue


log = logging.getLogger(__name__)


class Config:
    _DEFAULTS = {
        'DOWNLOAD_DIR': '.',                            # Video default dir
        'AUDIO_DOWNLOAD_DIR': '%%AUDIO_DOWNLOAD_DIR',   # Audio specific dir - defined in docker
        'TEMP_DIR': '%%DOWNLOAD_DIR',
        'DOWNLOAD_DIRS_INDEXABLE': 'false',
        'CUSTOM_DIRS': 'true',
        'CREATE_CUSTOM_DIRS': 'true',
        'DELETE_FILE_ON_TRASHCAN': 'false',
        'STATE_DIR': '.',
        'URL_PREFIX': '',
        'PUBLIC_HOST_URL': 'download/',
        'PUBLIC_HOST_AUDIO_URL': 'audio_download/',
        'OUTPUT_TEMPLATE': '%(title)s.%(ext)s',
        'OUTPUT_TEMPLATE_CHAPTER': '%(title)s - %(section_number)s %(section_title)s.%(ext)s',
        'OUTPUT_TEMPLATE_PLAYLIST': '%(playlist_title)s/%(title)s.%(ext)s',
        'DEFAULT_OPTION_PLAYLIST_STRICT_MODE' : 'false',
        'DEFAULT_OPTION_PLAYLIST_ITEM_LIMIT' : '0',
        'YTDL_OPTIONS': '{}',
        'YTDL_OPTIONS_FILE': '',
        'ROBOTS_TXT': '',
        'HOST': '0.0.0.0',
        'PORT': '8081',
        'HTTPS': 'false',
        'CERTFILE': '',
        'KEYFILE': '',
        'BASE_DIR': '',
        'DEFAULT_THEME': 'auto',
        'DOWNLOAD_MODE': 'limited',
        'MAX_CONCURRENT_DOWNLOADS': 3,
        'TELEGRAM_BOT_ENABLED': os.getenv('TELEGRAM_BOT_ENABLED', "False").upper() == "TRUE",
    }

    _BOOLEAN = ('DOWNLOAD_DIRS_INDEXABLE', 'CUSTOM_DIRS', 'CREATE_CUSTOM_DIRS', 'DELETE_FILE_ON_TRASHCAN', 'DEFAULT_OPTION_PLAYLIST_STRICT_MODE', 'HTTPS', 'TELEGRAM_BOT_ENABLED')

    def __init__(self):

        try:
            prj_dir = pathlib.Path(__name__).parent.parent
            dotenv.load_dotenv(prj_dir.joinpath('.env'), override=True)
        except Exception as e:
            log.error('Unable to load ".env" some functionalities may be limited. Please check your environment variables')

        for k, v in self._DEFAULTS.items():
            setattr(self, k, os.environ.get(k, v))

        for k, v in self.__dict__.items():
            if isinstance(v, str) and v.startswith('%%'):
                setattr(self, k, getattr(self, v[2:]))
            if k in self._BOOLEAN:
                if v not in ('true', 'false', 'True', 'False', 'on', 'off', '1', '0'):
                    log.error(f'Environment variable "{k}" is set to a non-boolean value "{v}"')
                    sys.exit(1)
                setattr(self, k, v in ('true', 'True', 'on', '1'))

        if not self.URL_PREFIX.endswith('/'):
            self.URL_PREFIX += '/'

        try:
            self.YTDL_OPTIONS = json.loads(self.YTDL_OPTIONS)
            assert isinstance(self.YTDL_OPTIONS, dict)
        except (json.decoder.JSONDecodeError, AssertionError):
            log.error('YTDL_OPTIONS is invalid')
            sys.exit(1)

        if self.YTDL_OPTIONS_FILE:
            log.info(f'Loading yt-dlp custom options from "{self.YTDL_OPTIONS_FILE}"')
            if not os.path.exists(self.YTDL_OPTIONS_FILE):
                log.error(f'File "{self.YTDL_OPTIONS_FILE}" not found')
                sys.exit(1)
            try:
                with open(self.YTDL_OPTIONS_FILE) as json_data:
                    opts = json.load(json_data)
                assert isinstance(opts, dict)
            except (json.decoder.JSONDecodeError, AssertionError):
                log.error('YTDL_OPTIONS_FILE contents is invalid')
                sys.exit(1)
            self.YTDL_OPTIONS.update(opts)


class ObjectSerializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, object):
            return obj.__dict__
        else:
            return json.JSONEncoder.default(self, obj)



class Notifier(DownloadQueueNotifier):
    async def added(self, dl):
        log.info(f"Notifier: Download added - {dl.title}")
        await sio.emit('added', serializer.encode(dl))

    async def updated(self, dl):
        log.info(f"Notifier: Download updated - {dl.title}")
        await sio.emit('updated', serializer.encode(dl))

    async def completed(self, dl):
        log.info(f"Notifier: Download completed - {dl.title}")
        await sio.emit('completed', serializer.encode(dl))

    async def canceled(self, id):
        log.info(f"Notifier: Download canceled - {id}")
        await sio.emit('canceled', serializer.encode(id))

    async def cleared(self, id):
        log.info(f"Notifier: Download cleared - {id}")
        await sio.emit('cleared', serializer.encode(id))


config = Config()
serializer = ObjectSerializer()
sio = socketio.AsyncServer(cors_allowed_origins='*')
dqueue = DownloadQueue(config, Notifier())
