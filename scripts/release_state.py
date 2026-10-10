"""Fetch GitHub and GHCR state, then apply the checked release policy."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

from release_policy import Conflict, check


def github(path):
    request = urllib.request.Request(
        f'https://api.github.com/repos/{os.environ["GITHUB_REPOSITORY"]}/{path}',
        headers={'Accept': 'application/vnd.github+json',
                 'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'X-GitHub-Api-Version': '2022-11-28'},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def image(tag):
    reference = os.environ['IMAGE'] + ':' + tag
    result = subprocess.run(['docker', 'buildx', 'imagetools', 'inspect',
                             '--format', '{{json .Manifest}}',
                             reference], capture_output=True)
    if result.returncode:
        detail = result.stderr.decode(errors='replace')
        if any(marker in detail.lower() for marker in ('manifest unknown', 'name unknown', 'not found')):
            return None
        raise RuntimeError(f'GHCR lookup for {tag} failed: {detail}')
    manifest = json.loads(result.stdout)
    labels = None
    for architecture in ('amd64', 'arm64'):
        children = [item['digest'] for item in manifest.get('manifests', [])
                    if item.get('platform', {}).get('os') == 'linux'
                    and item['platform'].get('architecture') == architecture]
        if len(children) != 1:
            raise Conflict(f'GHCR image {tag} lacks one linux/{architecture} manifest')
        child = os.environ['IMAGE'] + '@' + children[0]
        config = subprocess.run(['docker', 'buildx', 'imagetools', 'inspect',
                                 '--format', '{{json .Image}}', child],
                                capture_output=True, check=True)
        details = json.loads(config.stdout)
        all_labels = (details or {}).get('config', {}).get('Labels') or {}
        current = {key: all_labels.get(key) for key in (
            'org.opencontainers.image.revision',
            'org.opencontainers.image.version',
            'org.opencontainers.image.source')}
        if labels is not None and current != labels:
            raise Conflict(f'GHCR image {tag} has different labels for amd64 and arm64')
        labels = current
    return {'digest': manifest['digest'],
            'labels': labels}


def main():
    version = open('VERSION', encoding='utf-8').read().strip()
    sha = os.environ['GITHUB_SHA']
    tag_name = 'v' + version
    reference = github('git/ref/tags/' + tag_name)
    tag = None
    if reference:
        obj = reference['object']
        if obj['type'] == 'tag':
            annotated = github('git/tags/' + obj['sha'])
            obj = annotated['object']
        if obj['type'] != 'commit':
            raise Conflict(f'Git tag {tag_name} does not resolve to a commit')
        tag = {'commit': obj['sha']}
    release = github('releases/tags/' + tag_name)
    state = {'sha': sha, 'version': version, 'candidate_digest': os.environ['CANDIDATE_DIGEST'],
             'sha_image': image(sha), 'version_image': image(tag_name), 'tag': tag,
             'release': release and {'tag_name': release['tag_name'],
                                     'target_commitish': release['target_commitish']},
             'original_sha_image': image(tag['commit']) if tag else None}
    result = check(state)
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        for key, value in result.items():
            output.write(f'{key}={str(value).lower()}\n')
    print(json.dumps({'version': version, 'sha': sha, **result}))


if __name__ == '__main__':
    try:
        main()
    except (Conflict, KeyError, RuntimeError) as error:
        print(f'Release conflict: {error}', file=sys.stderr)
        raise SystemExit(1)
