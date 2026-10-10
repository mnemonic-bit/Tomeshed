"""Check the local Tomeshed health route from inside the container."""

import json
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=3) as response:
    assert response.status == 200 and json.load(response).get('ok') is True
