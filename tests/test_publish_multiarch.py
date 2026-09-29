import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('publish_multiarch', Path(__file__).resolve().parents[1] / 'bin/publish_multiarch.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublishMultiarchTest(unittest.TestCase):
    images = ['docker.io/example/jenkins', 'ghcr.io/example/jenkins']
    digests = {'amd64': 'sha256:' + 'a' * 64, 'arm64': 'sha256:' + 'b' * 64}

    def registry(self, *args):
        if args[:3] == ('manifest', 'inspect', '--verbose'):
            arch = args[-1].rsplit('-', 1)[1]
            return json.dumps({'Descriptor': {'digest': self.digests[arch],
                              'platform': {'os': 'linux', 'architecture': arch}}})
        if args[:4] == ('buildx', 'imagetools', 'inspect', '--raw'):
            return json.dumps({'manifests': [{'digest': digest, 'platform': {'os': 'linux', 'architecture': arch}}
                               for arch, digest in self.digests.items()]})
        return ''

    def test_all_registries_checked_before_publish_and_digests_used(self):
        with patch.object(module, 'docker', side_effect=self.registry) as docker:
            module.publish(self.images, '0.1.0-9', 'ci-123-1')
        calls = [call.args for call in docker.call_args_list]
        self.assertTrue(all(call[:3] == ('manifest', 'inspect', '--verbose') for call in calls[:4]))
        creates = [call for call in calls if call[:3] == ('buildx', 'imagetools', 'create')]
        self.assertEqual(len(creates), 2)
        for call, image in zip(creates, self.images):
            self.assertEqual(call[-2:], tuple(f'{image}@{self.digests[a]}' for a in module.ARCHITECTURES))
            self.assertIn(image + ':0.1.0-9', call)
            self.assertIn(image + ':latest', call)
        self.assertEqual(sum(call[:4] == ('buildx', 'imagetools', 'inspect', '--raw') for call in calls), 4)

    def test_missing_second_registry_arm_image_does_not_change_any_final_tag(self):
        def registry(*args):
            if args[-1] == self.images[1] + ':ci-123-1-arm64':
                raise subprocess.CalledProcessError(1, ['docker'])
            return self.registry(*args)
        with patch.object(module, 'docker', side_effect=registry) as docker:
            with self.assertRaises(subprocess.CalledProcessError):
                module.publish(self.images, '0.1.0-9', 'ci-123-1')
        self.assertFalse(any(call.args[:3] == ('buildx', 'imagetools', 'create') for call in docker.call_args_list))

    def test_wrong_platform_rejected_before_publish(self):
        wrong = json.dumps({'Descriptor': {'digest': self.digests['amd64'],
                           'platform': {'os': 'linux', 'architecture': 'amd64'}}})
        with patch.object(module, 'docker', return_value=wrong) as docker:
            with self.assertRaises(ValueError):
                module.publish(self.images, '0.1.0-9', 'ci-123-1')
        self.assertEqual(docker.call_count, 2)

    def test_incomplete_wrong_digest_or_duplicate_index_rejected(self):
        descriptor = lambda arch, digest: {'digest': digest, 'platform': {'os': 'linux', 'architecture': arch}}
        for entries in [[], [descriptor('amd64', self.digests['amd64'])],
                        [descriptor(a, 'sha256:'+'c'*64) for a in module.ARCHITECTURES],
                        [descriptor(a, self.digests[a]) for a in module.ARCHITECTURES] + [descriptor('arm64', self.digests['arm64'])]]:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                module.verify_index({'manifests': entries}, self.digests)

    def test_invalid_tag_does_not_call_registry(self):
        with patch.object(module, 'docker') as docker:
            with self.assertRaises(ValueError):
                module.publish(self.images, 'latest', 'ci-123-1')
            docker.assert_not_called()
