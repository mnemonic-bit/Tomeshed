"""Workflow events cover develop without granting release publication access."""
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).parents[1]


def workflow(name):
    # BaseLoader preserves GitHub's `on` key instead of treating it as a boolean.
    return yaml.load((ROOT / '.github/workflows' / name).read_text(encoding='utf-8'),
                     Loader=yaml.BaseLoader)


def test_develop_push_runs_validation_and_container_build():
    validation = workflow('validation.yml')
    assert 'develop' in validation['on'].get('push', {}).get('branches', [])
    assert 'workflow_call' in validation['on']
    gate = validation['jobs']['deterministic-gate']
    assert 'if' not in gate
    steps = [step for step in gate['steps'] if step.get('run') == './tests/run-all.sh']
    assert len(steps) == 1
    assert 'if' not in steps[0]
    assert 'tests/container/smoke.sh --build' in (ROOT / 'tests/run-all.sh').read_text(encoding='utf-8').splitlines()


@pytest.mark.parametrize('branch', ['main', 'develop'])
def test_pull_requests_receive_validation(branch):
    assert branch in workflow('validation.yml')['on']['pull_request']['branches']


@pytest.mark.parametrize('event', ['push', 'pull_request'])
@pytest.mark.parametrize('branch', ['main', 'develop'])
def test_branch_events_receive_codeql(event, branch):
    assert branch in workflow('codeql.yml')['on'][event]['branches']


def test_publication_remains_scoped_to_main():
    main = workflow('main.yml')
    assert set(main['on']) == {'push'}
    assert main['on']['push']['branches'] == ['main']
    assert main['jobs']['validation']['uses'] == './.github/workflows/validation.yml'
    assert main['jobs']['publish']['needs'] == ['validation']
    validation = workflow('validation.yml')
    assert validation['permissions'] == {'contents': 'read'}
    for job in validation['jobs'].values():
        assert 'write' not in job.get('permissions', {}).values()
