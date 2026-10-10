"""Release policy protects immutable tags and partial publication retries."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('release_policy', Path(__file__).parents[1] / 'scripts/release_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
SHA = 'a' * 40
OLD = 'b' * 40
DIGEST = 'sha256:' + '1' * 64
OLD_DIGEST = 'sha256:' + '2' * 64


def image(commit=SHA, digest=DIGEST):
    return {'digest': digest, 'labels': {
        'org.opencontainers.image.revision': commit,
        'org.opencontainers.image.version': '0.2.0',
    }}


def state():
    return {'sha': SHA, 'version': '0.2.0', 'candidate_digest': DIGEST,
            'sha_image': None, 'version_image': None, 'tag': None, 'release': None}


def test_new_release_and_retry_after_public_access_failure():
    initial = state()
    assert policy.check(initial) == {'new_release': True, 'sha_tag_exists': False}
    initial['sha_image'] = image()
    assert policy.check(initial) == {'new_release': True, 'sha_tag_exists': True}


def test_existing_release_preserves_original_commit_for_documentation_merge():
    existing = state()
    existing.update(tag={'commit': OLD}, release={'tag_name': 'v0.2.0', 'target_commitish': OLD},
                    version_image=image(OLD, OLD_DIGEST), original_sha_image=image(OLD, OLD_DIGEST))
    assert policy.check(existing) == {'new_release': False, 'sha_tag_exists': False}


@pytest.mark.parametrize('key', ['tag', 'release', 'version_image'])
def test_partial_release_conflicts_name_all_artifacts(key):
    partial = state()
    partial[key] = {'commit': SHA} if key == 'tag' else {'digest': DIGEST}
    with pytest.raises(policy.Conflict, match='partial release state.*Git tag.*GitHub Release.*GHCR version tag'):
        policy.check(partial)


def test_sha_tag_must_match_candidate_digest():
    existing = state()
    existing['sha_image'] = image(digest=OLD_DIGEST)
    with pytest.raises(policy.Conflict, match='existing SHA tag .* digest'):
        policy.check(existing)


@pytest.mark.parametrize('mutation', ['release_commit', 'image_commit', 'image_version', 'image_digest'])
def test_existing_triplet_must_agree(mutation):
    existing = state()
    existing.update(tag={'commit': OLD}, release={'tag_name': 'v0.2.0', 'target_commitish': OLD},
                    version_image=image(OLD, OLD_DIGEST), original_sha_image=image(OLD, OLD_DIGEST))
    if mutation == 'release_commit':
        existing['release']['target_commitish'] = SHA
    elif mutation == 'image_commit':
        existing['version_image']['labels']['org.opencontainers.image.revision'] = SHA
    elif mutation == 'image_version':
        existing['version_image']['labels']['org.opencontainers.image.version'] = '0.1.0'
    else:
        existing['version_image']['digest'] = DIGEST
    with pytest.raises(policy.Conflict):
        policy.check(existing)
