import importlib.util
import unittest
from pathlib import Path
from urllib.error import HTTPError


SCRIPT = Path(__file__).parents[1] / "bin" / "resolve_plugin_version.py"
SPEC = importlib.util.spec_from_file_location("resolve_plugin_version", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, content):
        self.content = content.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.content


class MetadataOpener:
    def __init__(self, documents):
        self.documents = documents

    def __call__(self, request, timeout):
        url = request.full_url
        if url not in self.documents:
            raise HTTPError(url, 404, "not found", {}, None)
        return FakeResponse(self.documents[url])


def metadata(*versions):
    version_elements = "".join(f"<version>{version}</version>" for version in versions)
    return f"<metadata><versioning><versions>{version_elements}</versions></versioning></metadata>"


class ResolvePluginVersionTest(unittest.TestCase):
    def test_selects_highest_supported_version_from_both_repositories(self):
        release_url = MODULE.metadata_url("https://release.example")
        snapshot_url = MODULE.metadata_url("https://snapshot.example")
        opener = MetadataOpener(
            {
                release_url: metadata("0.1.0", "0.2.0"),
                snapshot_url: metadata("0.3.0-SNAPSHOT"),
            }
        )

        version, repository = MODULE.resolve_latest(
            (("release", "https://release.example"), ("snapshot", "https://snapshot.example")),
            opener=opener,
        )

        self.assertEqual(version, "0.3.0-SNAPSHOT")
        self.assertEqual(repository, "https://snapshot.example")

    def test_release_wins_when_release_and_snapshot_have_same_base_version(self):
        release_url = MODULE.metadata_url("https://release.example")
        snapshot_url = MODULE.metadata_url("https://snapshot.example")
        opener = MetadataOpener(
            {
                release_url: metadata("0.3.0"),
                snapshot_url: metadata("0.3.0-SNAPSHOT"),
            }
        )

        version, repository = MODULE.resolve_latest(
            (("release", "https://release.example"), ("snapshot", "https://snapshot.example")),
            opener=opener,
        )

        self.assertEqual(version, "0.3.0")
        self.assertEqual(repository, "https://release.example")

    def test_manual_snapshot_selects_snapshot_repository(self):
        self.assertEqual(
            MODULE.repository_for_version("0.1.0-SNAPSHOT"),
            "https://jars.interlis.guru/snapshots",
        )

    def test_rejects_unsupported_version(self):
        with self.assertRaises(ValueError):
            MODULE.parse_version("v0.1.0")

    def test_fails_when_no_supported_metadata_exists(self):
        with self.assertRaises(RuntimeError):
            MODULE.resolve_latest(
                (("release", "https://release.example"),),
                opener=MetadataOpener({}),
            )


if __name__ == "__main__":
    unittest.main()
