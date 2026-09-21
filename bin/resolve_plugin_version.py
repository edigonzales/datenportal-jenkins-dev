#!/usr/bin/env python3
"""Resolve the newest published datenportal Jenkins plugin version.

The resolver deliberately uses only the Python standard library so it can run
on a stock GitHub-hosted runner before Maven is invoked by the image build.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable, Iterable, List, Optional, Tuple


GROUP = "ch.so.agi.jenkins"
ARTIFACT = "jenkins-gretl-datenportal-plugin"
REPOSITORIES = (
    ("releases", "https://jars.interlis.guru/releases"),
    ("snapshots", "https://jars.interlis.guru/snapshots"),
)
VERSION_PATTERN = re.compile(r"^(?P<base>\d+\.\d+\.\d+)(?P<snapshot>-SNAPSHOT)?$")


def metadata_url(repository_url: str) -> str:
    group_path = GROUP.replace(".", "/")
    return (
        f"{repository_url.rstrip('/')}/{group_path}/{ARTIFACT}/maven-metadata.xml"
    )


def parse_version(version: str) -> Tuple[Tuple[int, int, int], int]:
    match = VERSION_PATTERN.fullmatch(version)
    if not match:
        raise ValueError(
            f"unsupported plugin version {version!r}; expected x.y.z or x.y.z-SNAPSHOT"
        )

    numeric = tuple(int(part) for part in match.group("base").split("."))
    # A release wins over a snapshot when both have the same numeric version.
    stability = 0 if match.group("snapshot") else 1
    return numeric, stability


def base_version(version: str) -> str:
    return ".".join(str(part) for part in parse_version(version)[0])


def read_versions(
    repository_url: str,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> List[str]:
    request = urllib.request.Request(
        metadata_url(repository_url),
        headers={"User-Agent": "datenportal-jenkins-image-build"},
    )
    try:
        with opener(request, timeout=15) as response:  # type: ignore[union-attr]
            document = ET.fromstring(response.read())  # type: ignore[union-attr]
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise

    versions = []
    for element in document.findall(".//version"):
        version = (element.text or "").strip()
        if version:
            versions.append(version)
    return versions


def resolve_latest(
    repositories: Iterable[Tuple[str, str]] = REPOSITORIES,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> Tuple[str, str]:
    candidates = []
    for label, repository_url in repositories:
        for version in read_versions(repository_url, opener=opener):
            try:
                ordering = parse_version(version)
            except ValueError:
                continue
            candidates.append((ordering, version, label, repository_url))

    if not candidates:
        raise RuntimeError(
            "no supported plugin version found in the configured Maven repositories"
        )

    _, version, _, repository_url = max(candidates, key=lambda candidate: candidate[0])
    return version, repository_url


def repository_for_version(version: str) -> str:
    parse_version(version)
    return dict(REPOSITORIES)["snapshots" if version.endswith("-SNAPSHOT") else "releases"]


def emit(version: str, repository_url: str) -> None:
    print(f"plugin_version={version}")
    print(f"plugin_base_version={base_version(version)}")
    print(f"plugin_repository_url={repository_url}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        help="use this exact version instead of resolving the newest published version",
    )
    parser.add_argument(
        "--repository-url",
        help="Maven repository to use with --version",
    )
    args = parser.parse_args(argv)

    try:
        if args.version:
            repository_url = args.repository_url or repository_for_version(args.version)
            parse_version(args.version)
            emit(args.version, repository_url)
        else:
            version, repository_url = resolve_latest()
            emit(version, repository_url)
    except (RuntimeError, ValueError, urllib.error.URLError) as error:
        print(f"Plugin version resolution failed: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
