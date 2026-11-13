"""Error types shared by the whole pipeline.

Every rejection of the input carries a JSON field path (``$.xml``,
``$.queries[2]`` ...).  ``QueryError`` is raised while handling a single
XPath expression; the service layer translates it into ``Reject`` with the
proper ``$.queries[i]`` path.
"""


class Reject(Exception):
    """The whole request is rejected; ``path`` is the JSON field path."""

    def __init__(self, path, message):
        super().__init__('%s: %s' % (path, message))
        self.path = path
        self.message = message


class QueryError(Exception):
    """Syntax / subset / static-type error inside one XPath query."""
