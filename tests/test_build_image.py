"""Prepared-context contract: no dependency resolution; test failure stops the job."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BuildImageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'bin').mkdir()
        self.commands = self.root / 'commands'
        self.commands.mkdir()
        shutil.copyfile(ROOT / 'bin/build-image.sh', self.root / 'bin/build-image.sh')
        self.context = self.root / 'shared context'
        self.context.mkdir()
        (self.context / 'Dockerfile').write_text('FROM scratch\n')
        self.metadata = dict(JENKINS_IMAGE='jenkins/jenkins:base', IMAGE_VERSION='0.1.0-9',
                             PLUGIN_VERSION='0.1.0', GRETL_VERSION='5.0.0-SNAPSHOT',
                             THEMEN_REPO_REVISION='abc123', PLUGIN_REPO_REVISION='unknown',
                             TEMURIN17_VERSION='17.0.15+6')
        self.write_metadata()
        self.log = self.root / 'calls'
        self.env = dict(os.environ, PATH=str(self.commands)+':'+os.environ['PATH'], TEST_CALLS=str(self.log),
                        IMAGE_PLATFORM='linux/arm64', ACTUAL_PLATFORM='linux/arm64', TEST_EXIT='0')
        self.script(self.commands / 'docker', '''printf 'docker' >> "$TEST_CALLS"
for arg in "$@"; do printf ' <%s>' "$arg" >> "$TEST_CALLS"; done
printf '\\n' >> "$TEST_CALLS"
if [[ "$1 $2" = 'image inspect' ]]; then printf '%s' "$ACTUAL_PLATFORM"; fi
''')
        self.script(self.root / 'bin/prepare-image-context.sh', 'echo unexpected-preparation >> "$TEST_CALLS"; exit 90\n')
        self.script(self.root / 'bin/test-image-duckdb.sh', 'echo offline-tests >> "$TEST_CALLS"; exit "$TEST_EXIT"\n')

    def script(self, path, body):
        path.write_text('#!/bin/bash\nset -e\n' + body)
        path.chmod(0o755)

    def write_metadata(self):
        (self.context / 'build-args.json').write_text(json.dumps(self.metadata))

    def run_build(self):
        result = subprocess.run(['bash', str(self.root / 'bin/build-image.sh'), '--prepared-context', str(self.context)],
                                env=self.env, capture_output=True, text=True)
        return result, self.log.read_text() if self.log.exists() else ''

    def test_prepared_context_is_built_and_tested_without_preparation(self):
        result, log = self.run_build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('unexpected-preparation', log)
        self.assertIn('<buildx> <build> <--load> <--provenance=false> <--platform> <linux/arm64>', log)
        self.assertIn('<PLUGIN_VERSION=0.1.0>', log)
        self.assertIn('<'+str(self.context)+'>', log)
        self.assertTrue(log.endswith('offline-tests\n'))

    def test_default_platform_works_with_macos_bash_empty_array_rules(self):
        self.env.pop('IMAGE_PLATFORM')
        result, log = self.run_build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('<--platform>', log)
        self.assertTrue(log.endswith('offline-tests\n'))

    def test_test_failure_propagates(self):
        self.env['TEST_EXIT'] = '17'
        result, log = self.run_build()
        self.assertEqual(result.returncode, 17)
        self.assertNotIn('Docker-Image gebaut', result.stdout)

    def test_wrong_architecture_rejected_before_tests(self):
        self.env['ACTUAL_PLATFORM'] = 'linux/amd64'
        result, log = self.run_build()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('offline-tests', log)

    def test_invalid_metadata_is_not_silently_ignored(self):
        for value in ['', 'bad\nargument', 'bad\rargument']:
            self.metadata['IMAGE_VERSION'] = value
            self.write_metadata()
            result, log = self.run_build()
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('<buildx> <build>', log)

    def test_multiple_platforms_rejected_before_any_build(self):
        self.env['IMAGE_PLATFORM'] = 'linux/amd64,linux/arm64'
        result, log = self.run_build()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(log, '')
