import os

from nose import SkipTest

from ..github import GitHubRepo
from ..source_cache import SourceCache

REMOTE = bool(int(os.environ.get('R', '0')))

def test_github():
    if not REMOTE:
        raise SkipTest()

    gh = GitHubRepo('hashdist', 'hashdist')
    sc = SourceCache([gh])

    bogus_key = 'foo:bar'
    present_key = 'git:99b8062bd4e956c8913144afd032c509475e3d5f'
    not_present_key = 'git:99b8062bd4e956c8913144afd032c509475e3d50'
    result = sc.find_remote_objects([bogus_key, not_present_key, present_key])
    print gh
    assert result[bogus_key] is None
    assert result[not_present_key] is None
    assert result[present_key] is gh
