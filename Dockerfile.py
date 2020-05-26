#!/usr/bin/env python3
""" Dockerfile.py - generates and build dockerfiles

Usage:
  Dockerfile.py [--os=<os> ...] [--hub_tag=<tag>] [--arch=<arch> ...] [-v] [-t] [--no-build | --no-generate] [--no-cache]

Options:
    --no-build      Skip building the docker images
    --no-cache      Build without using any cache data
    --no-generate   Skip generating Dockerfiles from template
    --os=<os>       What OS(s) to build             [default: alpine debian]
    --hub_tag=<tag> What the Docker Hub Image should be tagged as [default: None]
    --arch=<arch>   What Architecture(s) to build   [default: amd64 armel armhf arm64]
    -v              Print docker's command output   [default: False]
    -t              Print docker's build time       [default: False]

Examples:
"""


from jinja2 import Environment, FileSystemLoader
from docopt import docopt
import os
import subprocess
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))

base_vars = {
    'name': 'pihole/pihole',
    'maintainer' : 'adam@diginc.us',
    's6_version' : 'v1.22.1.0',
}

os_base_vars = {
    'debian': {
        'php_env_config': '/etc/lighttpd/conf-enabled/15-fastcgi-php.conf',
        'php_error_log': '/var/log/lighttpd/error.log'
    },
    'alpine': {
        'php_env_config': '/etc/php5/fpm.d/envs.conf',
        'php_error_log': '/var/log/nginx/error.log'
    }
}

__version__ = None
dot = os.path.abspath('.')
with open('{}/VERSION'.format(dot), 'r') as v:
    raw_version = v.read().strip()
    __version__ = raw_version.replace('release/', 'release-')

images = {
    'debian': [
        {
            'base': 'pihole/debian-base:latest',
            'arch': 'amd64',
            's6arch': 'amd64',
        },
        {
            'base': 'multiarch/debian-debootstrap:armel-stretch-slim',
            'arch': 'armel',
            's6arch': 'arm',
        },
        {
            'base': 'multiarch/debian-debootstrap:armhf-stretch-slim',
            'arch': 'armhf',
            's6arch' : 'arm',
        },
        {
            'base': 'multiarch/debian-debootstrap:arm64-stretch-slim',
            'arch': 'arm64',
            's6arch' : 'aarch64',
        }
    ],
    'alpine': [
        {
            'base': 'alpine:edge',
            'arch': 'amd64',
            's6arch': 'amd64',
        },
        {
            'base': 'multiarch/alpine:armhf-edge',
            'arch': 'arm',
            's6arch' : 'arm',
        },
        {
            'base': 'multiarch/alpine:arm64-edge',
            'arch': 'arm64',
            's6arch' : 'aarch64',
        }
    ]
}

def generate_dockerfiles(args):
    if args['--no-generate']:
        print(" ::: Skipping Dockerfile generation")
        return

    for os, archs in images.items():
        for image in archs:
            if os not in args['--os']:
                continue
            if image['arch'] not in args['--arch']:
                continue
            s6arch = image['s6arch'] if image['s6arch'] else image['arch']
            merged_data = dict(
                list({ 'version': __version__ }.items()) +
                list({ 'os': os }.items()) +
                list(base_vars.items()) +
                list(os_base_vars[os].items()) +
                list(image.items()) +
                list({ 's6arch': s6arch }.items())
            )
            j2_env = Environment(loader=FileSystemLoader(THIS_DIR),
                                 trim_blocks=True)
            template = j2_env.get_template('Dockerfile.template')

            dockerfile = 'Dockerfile_{}'.format(image['arch'])
            with open(dockerfile, 'w') as f:
                f.write(template.render(pihole=merged_data))


def build_dockerfiles(args):
    if args['--no-build']:
        print(" ::: Skipping Dockerfile building")
        return

    for os in args['--os']:
        for arch in args['--arch']:
            build('pihole', os, arch, args)


def run_and_stream_command_output(command, args):
    print("Running", command)
    build_result = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    bufsize=1, universal_newlines=True)
    if args['-v']:
        while build_result.poll() is None:
            for line in build_result.stdout:
                print(line, end='')
    build_result.wait()
    if build_result.returncode != 0:
        print("     ::: Error running".format(command))
        print(build_result.stderr)


def build(docker_repo, os, arch, args):
    dockerfile = 'Dockerfile_{}'.format(arch)
    repo_tag = '{}:{}_{}_{}'.format(docker_repo, __version__, os, arch)
    cached_image = '{}/{}'.format('pihole', repo_tag)
    print(" ::: Building {}".format(repo_tag))
    time=''
    if args['-t']:
        time='time '
    no_cache = ''
    if args['--no-cache']:
        no_cache = '--no-cache'
    build_command = '{time}docker build {no_cache} --pull --cache-from="{cache},{create_tag}" -f {dockerfile} -t {create_tag} .'\
        .format(time=time, no_cache=no_cache, cache=cached_image, dockerfile=dockerfile, create_tag=repo_tag)
    print(" ::: Building {} into {}".format(dockerfile, repo_tag))
    run_and_stream_command_output(build_command, args)
    if args['-v']:
        print(build_command, '\n')
    if args['--hub_tag']:
        hub_tag_command = "{time}docker tag {create_tag} {hub_tag}"\
            .format(time=time, create_tag=repo_tag, hub_tag=args['--hub_tag'])
        print(" ::: Tagging {} into {}".format(repo_tag, args['--hub_tag']))
        run_and_stream_command_output(hub_tag_command, args)


if __name__ == '__main__':
    args = docopt(__doc__, version='Dockerfile 1.1')
    if args['-v']:
        print(args)

    generate_dockerfiles(args)
    build_dockerfiles(args)
