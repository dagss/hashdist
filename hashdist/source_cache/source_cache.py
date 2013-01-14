import threading

NTHREADS = 50

class SourceCache(object):

    def __init__(self, repos):
        self.repos = repos
        self.remote_repos = [r for r in repos if r.is_remote]

    def find_remote_objects(self, keys):
        def thread_main():
            while True:
                try:
                    key = keys.pop()
                except IndexError:
                    break
                for repo in self.remote_repos:
                    if repo.has_object(key):
                        key_to_repo[key] = repo
        keys = list(keys)
        key_to_repo = dict((key, None) for key in keys)
        nthreads = min(NTHREADS, len(keys))
        threads = [threading.Thread(target=thread_main) for i in range(nthreads)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return key_to_repo
