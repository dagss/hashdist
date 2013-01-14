import urllib2
import json

class ProtocolError(Exception):
    pass

class GitHubRepo(object):
    """
    Should be immutable for thread-safety
    """
    is_remote = True

    def __init__(self, project, repo_name):
        self.project = project
        self.repo_name = repo_name

    def has_object(self, key):
        if not key.startswith('git:'):
            return False
        digest = key[len('git:'):]
        url = 'https://api.github.com/repos/%s/%s/git/commits/%s' % (
            self.project, self.repo_name, digest)
        try:
            f = urllib2.urlopen(url)
            f.close()
            return True
        except urllib2.HTTPError, e:
            if e.code != 404:
                raise
            return False

