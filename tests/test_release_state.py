"""Mock GitHub and registry responses at the release-state boundary."""
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
release_state = importlib.import_module('release_state')
policy = importlib.import_module('release_policy')


def test_registry_index_checks_both_platform_config_labels(monkeypatch):
    calls = []
    labels = {'org.opencontainers.image.revision': 'a' * 40,
              'org.opencontainers.image.version': '0.2.0',
              'org.opencontainers.image.source': 'https://github.com/mnemonic-bit/Tomeshed'}
    manifest = {'digest': 'sha256:' + '1' * 64, 'manifests': [
        {'digest': 'sha256:' + '2' * 64, 'platform': {'os': 'linux', 'architecture': 'amd64'}},
        {'digest': 'sha256:' + '3' * 64, 'platform': {'os': 'linux', 'architecture': 'arm64'}}]}

    def run(command, **kwargs):
        calls.append(command)
        content = manifest if command[-1].endswith(':v0.2.0') else {'config': {'Labels': labels}}
        return SimpleNamespace(returncode=0, stdout=json.dumps(content).encode(), stderr=b'')

    monkeypatch.setenv('IMAGE', 'ghcr.io/mnemonic-bit/tomeshed')
    monkeypatch.setattr(release_state.subprocess, 'run', run)
    assert release_state.image('v0.2.0') == {'digest': manifest['digest'], 'labels': labels}
    assert len(calls) == 3
    assert calls[1][-1].endswith('@sha256:' + '2' * 64)
    assert calls[2][-1].endswith('@sha256:' + '3' * 64)


def test_registry_rejects_missing_platform(monkeypatch):
    monkeypatch.setenv('IMAGE', 'ghcr.io/mnemonic-bit/tomeshed')
    def run(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps({'digest': 'sha256:' + '1' * 64,
                                'manifests': []}).encode(), stderr=b'')
    monkeypatch.setattr(release_state.subprocess, 'run', run)
    with pytest.raises(policy.Conflict, match='linux/amd64'):
        release_state.image('v0.2.0')


def test_release_state_retry_with_mocked_github_and_registry(monkeypatch, tmp_path, capsys):
    sha = 'a' * 40
    digest = 'sha256:' + '1' * 64
    version = (Path(__file__).parents[1] / 'VERSION').read_text(encoding='utf-8').strip()
    labels = {'org.opencontainers.image.revision': sha,
              'org.opencontainers.image.version': version}
    monkeypatch.setenv('GITHUB_SHA', sha)
    monkeypatch.setenv('GITHUB_REPOSITORY', 'mnemonic-bit/Tomeshed')
    monkeypatch.setenv('GH_TOKEN', 'test-token')
    monkeypatch.setenv('CANDIDATE_DIGEST', digest)
    monkeypatch.setenv('GITHUB_OUTPUT', str(tmp_path / 'outputs'))
    monkeypatch.setattr(release_state, 'github', lambda path: None)
    monkeypatch.setattr(release_state, 'image', lambda tag: {'digest': digest, 'labels': labels} if tag == sha else None)
    release_state.main()
    assert (tmp_path / 'outputs').read_text() == 'new_release=true\nsha_tag_exists=true\n'
    result = json.loads(capsys.readouterr().out)
    assert result['new_release'] is True
    assert result['version'] == version
