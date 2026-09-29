#!/usr/bin/env python3
"""Validate staged images in all registries before publishing multiarch tags."""
import argparse
import json
import re
import subprocess
import sys

ARCHITECTURES = ('amd64', 'arm64')
DIGEST = re.compile(r'sha256:[0-9a-f]{64}')
TAG = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}')


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=120)


def platform_digest(manifest, arch):
    descriptor = manifest.get('Descriptor', {}) if isinstance(manifest, dict) else {}
    platform = descriptor.get('platform', {})
    digest = descriptor.get('digest', '')
    if (platform.get('os') != 'linux' or platform.get('architecture') != arch
            or not DIGEST.fullmatch(digest)):
        raise ValueError(f'Staged image is not a single linux/{arch} image with a SHA256 digest')
    return digest


def verify_index(index, expected):
    actual = {}
    for descriptor in index.get('manifests', []):
        platform = descriptor.get('platform', {})
        if platform.get('os') != 'linux':
            raise ValueError('Unexpected OS in published image index')
        arch = platform.get('architecture')
        if arch in actual:
            raise ValueError('Duplicate architecture in published image index')
        actual[arch] = descriptor.get('digest')
    if actual != expected:
        raise ValueError('Published index does not reference exactly the two tested platform digests')


def publish(images, version, staging_prefix):
    if not TAG.fullmatch(version) or version == 'latest':
        raise ValueError('Invalid version tag')
    if not all(TAG.fullmatch(f'{staging_prefix}-{arch}') for arch in ARCHITECTURES):
        raise ValueError('Invalid staging prefix')
    # Complete read-only preflight for BOTH registries before mutating any final tag.
    candidates = {}
    for image in images:
        candidates[image] = {}
        for arch in ARCHITECTURES:
            ref = f'{image}:{staging_prefix}-{arch}'
            manifest = json.loads(docker('manifest', 'inspect', '--verbose', ref))
            candidates[image][arch] = platform_digest(manifest, arch)
    for image, digests in candidates.items():
        refs = [f'{image}@{digests[arch]}' for arch in ARCHITECTURES]
        docker('buildx', 'imagetools', 'create', '--tag', f'{image}:{version}',
               '--tag', f'{image}:latest', *refs)
        for tag in (version, 'latest'):
            index = json.loads(docker('buildx', 'imagetools', 'inspect', '--raw', f'{image}:{tag}'))
            verify_index(index, digests)
            print(f'{image}:{tag}: verified linux/amd64 + linux/arm64', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', action='append', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--staging-prefix', required=True)
    args = parser.parse_args()
    try:
        publish(args.image, args.version, args.staging_prefix)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Multiarch publication failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
