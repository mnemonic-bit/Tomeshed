"""Check immutable GHCR and GitHub release state before publication.

Input is one JSON object with keys sha, version, candidate_digest, sha_image,
version_image, tag, release. Missing remote objects are represented by null.
Image objects contain a manifest digest and image config labels. The Git tag object
contains its commit; the release object contains tag_name and target_commitish.
"""
import json
import re
import sys


class Conflict(ValueError):
    pass


def check(state):
    sha = state['sha']
    version = state['version']
    candidate = state['candidate_digest']
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise Conflict('commit SHA is not a full Git SHA')
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise Conflict('VERSION must contain a semantic version core')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', candidate):
        raise Conflict('candidate image digest is missing or invalid')
    release_tag = 'v' + version
    sha_image = state.get('sha_image')
    if sha_image:
        if sha_image['digest'] != candidate:
            raise Conflict(f'existing SHA tag {sha} digest {sha_image["digest"]} conflicts with candidate {candidate}')
        labels = sha_image.get('labels') or {}
        if labels.get('org.opencontainers.image.revision') != sha or labels.get('org.opencontainers.image.version') != version:
            raise Conflict(f'existing SHA tag {sha} has conflicting revision or version labels')

    tag, release, image = (state.get(key) for key in ('tag', 'release', 'version_image'))
    present = {'Git tag': bool(tag), 'GitHub Release': bool(release), 'GHCR version tag': bool(image)}
    if len(set(present.values())) != 1:
        raise Conflict(f'partial release state for {release_tag}: ' + ', '.join(f'{key}={value}' for key, value in present.items()))
    if not any(present.values()):
        return {'new_release': True, 'sha_tag_exists': bool(sha_image)}

    original = tag.get('commit')
    if not original or not re.fullmatch(r'[0-9a-f]{40}', original):
        raise Conflict(f'Git tag {release_tag} does not resolve to a full commit SHA')
    if release.get('tag_name') != release_tag or release.get('target_commitish') != original:
        raise Conflict(f'GitHub Release {release_tag} target conflicts with Git tag commit {original}')
    labels = image.get('labels') or {}
    if labels.get('org.opencontainers.image.revision') != original or labels.get('org.opencontainers.image.version') != version:
        raise Conflict(f'GHCR version tag {release_tag} revision or version conflicts with Git tag {original}')
    original_sha_image = state.get('original_sha_image')
    if not original_sha_image or original_sha_image['digest'] != image['digest']:
        raise Conflict(f'GHCR version tag {release_tag} digest conflicts with original SHA image {original}')
    return {'new_release': False, 'sha_tag_exists': bool(sha_image)}


if __name__ == '__main__':
    try:
        print(json.dumps(check(json.load(sys.stdin)), sort_keys=True))
    except (Conflict, KeyError, TypeError) as error:
        print(f'Release conflict: {error}', file=sys.stderr)
        raise SystemExit(1)
