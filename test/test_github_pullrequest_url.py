import unittest
import os
import db_test_base
import cgi
import shutil
import errno
from BaseHTTPServer import BaseHTTPRequestHandler
from StringIO import StringIO
from roundup.cgi import client
from roundup.backends import list_backends
from roundup.github_pullrequest_url import GitHubHandler
from roundup.exceptions import *

NEEDS_INSTANCE = 1


class HTTPRequest(BaseHTTPRequestHandler):
    def __init__(self, filename):
        path = os.path.dirname(os.path.abspath(__file__)) + "/data/" + filename
        request_file = open(path, 'r')
        request_text = request_file.read()
        request_file.close()
        self.rfile = StringIO(request_text)
        self.raw_requestline = self.rfile.readline()
        self.error_code = self.error_message = None
        self.parse_request()


class TestCase(unittest.TestCase):

    backend = None

    def setUp(self):
        # instance
        self.dirname = '_test_github_pullrequest_url'
        self.instance = db_test_base.setupTracker(self.dirname, self.backend)
        self.env = {
            'PATH_INFO': 'http://localhost/github_pullrequest_url',
            'HTTP_HOST': 'localhost',
            'TRACKER_NAME': 'test',
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/json'
        }
        os.environ['SECRET_KEY'] = "secret123"

    def tearDown(self):
        self.db.close()
        try:
            shutil.rmtree(self.dirname)
        except OSError, error:
            if error.errno not in (errno.ENOENT, errno.ESRCH):
                raise

    def _make_client(self, filename):
        request = HTTPRequest(filename)
        form = cgi.FieldStorage(fp=request.rfile, environ=self.env,
                                headers=request.headers)
        dummy_client = client.Client(self.instance, request, self.env, form)
        dummy_client.opendb("admin")
        self.db = dummy_client.db
        self.db.issue.create(title="Hello")
        return dummy_client

    def testSecretKey(self):
        os.environ['SECRET_KEY'] = "1234"
        dummy_client = self._make_client("pingevent.txt")
        with self.assertRaises(Unauthorised) as context:
            GitHubHandler(dummy_client)
        self.assertEqual(str(context.exception),
                         "The provided secret does not match")

    def testUnsupportedMediaType(self):
        dummy_client = self._make_client("pingevent.txt")
        dummy_client.env['CONTENT_TYPE'] = 'application/xml'
        with self.assertRaises(UnsupportedMediaType) as context:
            GitHubHandler(dummy_client)
        self.assertEqual(str(context.exception),
                         "unsupported Content-Type application/xml")

    def testMethodNotAllowed(self):
        dummy_client = self._make_client("pingevent.txt")
        dummy_client.env['REQUEST_METHOD'] = 'GET'
        with self.assertRaises(MethodNotAllowed) as context:
            GitHubHandler(dummy_client)
        self.assertEqual(str(context.exception),
                         "unsupported HTTP method GET")

    def testPingEvent(self):
        dummy_client = self._make_client("pingevent.txt")
        with self.assertRaises(Reject) as context:
            GitHubHandler(dummy_client)
        self.assertEqual(str(context.exception), "Unkown X-GitHub-Event ping")

    def testIssueCommentEvent(self):
        dummy_client = self._make_client("issuecommentevent.txt")
        GitHubHandler(dummy_client)
        urls = self.db.issue.get('1', 'github_pullrequest_urls')
        self.assertTrue(len(urls) == 1)
        url_id = self.db.github_pullrequest_url.lookup('1')
        self.assertEqual(url_id, '1')

    def testPullRequestEventForTitle(self):
        # When the title of a PR has string "fixes bpo123"
        dummy_client = self._make_client("pullrequestevent.txt")
        GitHubHandler(dummy_client)
        urls = self.db.issue.get('1', 'github_pullrequest_urls')
        self.assertTrue(len(urls) == 1)
        url_id = self.db.github_pullrequest_url.lookup('2')
        self.assertEqual(url_id, '1')
        state = self.db.github_pullrequest_url.get('1', 'state')
        self.assertEqual(state, "open")

    def testPullRequestEventForBody(self):
        # When the body of a PR has string "fixes bpo123"
        dummy_client = self._make_client("pullrequestevent1.txt")
        GitHubHandler(dummy_client)
        urls = self.db.issue.get('1', 'github_pullrequest_urls')
        self.assertTrue(len(urls) == 1)
        url_id = self.db.github_pullrequest_url.lookup('3')
        self.assertEqual(url_id, '1')
        state = self.db.github_pullrequest_url.get('1', 'state')
        self.assertEqual(state, "open")

    def testMergedPullRequest(self):
        # When pull request is merged
        dummy_client = self._make_client("pullrequestopen.txt")
        GitHubHandler(dummy_client)
        urls = self.db.issue.get('1', 'github_pullrequest_urls')
        self.assertTrue(len(urls) == 1)
        url_id = self.db.github_pullrequest_url.lookup('2')
        self.assertEqual(url_id, '1')
        state = self.db.github_pullrequest_url.get('1', 'state')
        self.assertEqual(state, "open")
        self.db.close()
        dummy_client = self._make_client("pullrequestmerged.txt")
        GitHubHandler(dummy_client)
        state = self.db.github_pullrequest_url.get('1', 'state')
        self.assertEqual(state, "merged")

    def testClosedPullRequest(self):
        # When pull request is merged
        dummy_client = self._make_client("pullrequestopen.txt")
        GitHubHandler(dummy_client)
        urls = self.db.issue.get('1', 'github_pullrequest_urls')
        self.assertTrue(len(urls) == 1)
        url_id = self.db.github_pullrequest_url.lookup('2')
        self.assertEqual(url_id, '1')
        state = self.db.github_pullrequest_url.get('1', 'state')
        self.assertEqual(state, "open")
        self.db.close()
        dummy_client = self._make_client("pullrequestclosed.txt")
        GitHubHandler(dummy_client)
        state = self.db.github_pullrequest_url.get('1', 'state')
        self.assertEqual(state, "closed")


def test_suite():
    suite = unittest.TestSuite()
    for l in list_backends():
        dct = dict(backend=l)
        subcls = type(TestCase)('TestCase_%s' % l, (TestCase,), dct)
        suite.addTest(unittest.makeSuite(subcls))
    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
