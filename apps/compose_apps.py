# Copyright (c) 2020 Foundries.io
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import yaml

from expandvars import expandvars

from helpers import cmd as cmd_exe
from apps.image_downloader import DockerDownloader


logger = logging.getLogger(__name__)


class ComposeApps:
    DisabledSuffix = '.disabled'

    class App:
        DockerComposeTool = 'docker'
        ComposeFile = 'docker-compose.yml'

        @staticmethod
        def is_compose_app_dir(app_dir):
            typo_file = os.path.join(app_dir, 'docker-compose.yaml')
            exists = os.path.exists(os.path.join(app_dir, ComposeApps.App.ComposeFile))
            if not exists and os.path.exists(typo_file):
                raise ValueError('docker-compose.yaml file found. This must be named docker-compose.yml')
            return exists

        def __init__(self, name, app_dir, image_downloader_cls=DockerDownloader, quiet=False):
            if not self.is_compose_app_dir(app_dir):
                raise Exception('Compose App dir {} does not contain a compose file {}'
                                .format(app_dir, self.ComposeFile))
            self.name = name
            self.dir = app_dir
            self.file = os.path.join(self.dir, self.ComposeFile)

            self._image_downloader_cls = image_downloader_cls

            args = [self.DockerComposeTool, 'compose', '-f', self.ComposeFile, 'config']
            if quiet:
                args.append('--quiet')
            cmd_exe(*args, cwd=self.dir)

            with open(self.file) as compose_file:
                self._desc = yaml.safe_load(compose_file)

        def services(self):
            return self['services'].items()

        def images(self, expand_env=False):
            for _, service_cfg in self.services():
                img = service_cfg['image']
                if expand_env:
                    img = expandvars(img)
                yield img

        def download_images(self, platform=None, docker_host='unix:///var/run/docker.sock'):
            downloader = self._image_downloader_cls(docker_host)
            for image in self.images():
                downloader.pull(image, platform)

        def save(self):
            with open(self.file, 'w') as compose_file:
                yaml.dump(self._desc, compose_file)

        def __getitem__(self, item):
            return self._desc[item]

    @property
    def apps(self):
        return self._apps

    @property
    def str(self):
        return ' '.join(app.name for app in self)

    def __init__(self, root_dir, quiet=False):
        self.root_dir = root_dir
        self._apps = []
        for app in os.listdir(self.root_dir):
            if app.endswith(self.DisabledSuffix):
                logger.info('App {} has been disabled, omitting it'.format(app))
                continue

            app_dir = os.path.join(self.root_dir, app)
            if not self.App.is_compose_app_dir(app_dir):
                logger.debug('An app dir {} is not Compose App dir'.format(app_dir))
                continue

            logger.debug('Found Compose App: '.format(app))
            self._apps.append(self.App(app, app_dir, quiet=quiet))

    def __iter__(self):
        return self._apps.__iter__()

    def __getitem__(self, item):
        return self._apps[item]

    def __len__(self):
        return len(self._apps)
