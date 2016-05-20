from roundup.exceptions import *

import hashlib
import hmac
import json
import re
import os


if hasattr(hmac, "compare_digest"):
    compare_digest = hmac.compare_digest
else:
    def compare_digest(a, b):
        return a == b


class GitHubHandler:

    def __init__(self, client):
        self.db = client.db
        self.request = client.request
        self.form = client.form
        self.data = json.loads(self.form.value)
        self.env = client.env
        self._validate_webhook_secret()
        self._verify_request()
        self._extract()

    def _extract(self):
        event = self._get_event()
        if event not in ('pull_request', 'issue_comment'):
            raise Reject('Unkown X-GitHub-Event %s' % event)
        if event == 'pull_request':
            PullRequest(self.db, self.data)
        elif event == 'issue_comment':
            IssueComment(self.db, self.data)

    def _validate_webhook_secret(self):
        key = os.environ['SECRET_KEY']
        data = self.form.value
        signature = "sha1=" + hmac.new(key, data,
                                       hashlib.sha1).hexdigest()
        header_signature = self.request.headers.get('X-Hub-Signature', '')
        result = compare_digest(signature, header_signature)
        if not result:
            raise Unauthorised("The provided secret does not match")

    def _verify_request(self):
        method = self.env.get('REQUEST_METHOD', None)
        if method != 'POST':
            raise MethodNotAllowed('unsupported HTTP method %s' % method)
        content_type = self.env.get('CONTENT_TYPE', None)
        if content_type != 'application/json':
            raise UnsupportedMediaType('unsupported Content-Type %s' %
                                       content_type)
        event = self._get_event()
        if event is None:
            raise Reject('missing X-GitHub-Event header')

    def _get_event(self):
        event = self.request.headers.get('X-GitHub-Event', None)
        return event


class Event:

    issue_re = re.compile(r'fixes\s+bpo(?P<id>\d+)', re.I)

    def handle_create(self, url, issue_id):
        issue_exists = len(self.db.issue.filter(None, {'id': issue_id})) == 1
        url_exists = len(self.db.github_pullrequest_url
                         .filter(None, {'url': url})) == 1
        if issue_exists and not url_exists:
            url_id = self.db.github_pullrequest_url.create(url=url)
            urls = self.db.issue.get(issue_id, 'github_pullrequest_urls')
            urls.append(url_id)
            self.db.issue.set(issue_id, github_pullrequest_urls=urls)
            self.db.commit()

    def _get_issue_id(self):
        raise NotImplementedError

    def _get_url(self):
        raise NotImplementedError


class PullRequest(Event):

    def __init__(self, db, data):
        self.db = db
        self.data = data
        action = self.data['action'].encode('utf-8')
        issue_id = self._get_issue_id()
        url = self._get_url()
        if action == 'opened':
            self.handle_create(url, issue_id)

    def _get_issue_id(self):
        title = self.data['pull_request']['title'].encode('utf-8')
        body = self.data['pull_request']['body'].encode('utf-8')
        title_match = self.issue_re.search(title)
        body_match = self.issue_re.search(body)
        if body_match:
            return body_match.group('id')
        elif title_match:
            return title_match.group('id')
        return None

    def _get_url(self):
        return self.data['pull_request']['html_url'].encode('utf-8')


class IssueComment(Event):

    def __init__(self, db, data):
        self.db = db
        self.data = data
        action = self.data['action'].encode('utf-8')
        issue_id = self._get_issue_id()
        url = self._get_url()
        if action == 'created':
            self.handle_create(url, issue_id)

    def _get_issue_id(self):
        body = self.data['comment']['body'].encode('utf-8')
        match = self.issue_re.search(body)
        if match:
            return match.group('id')
        return None

    def _get_url(self):
        if 'pull_request' in self.data['issue']:
            return self.data['issue']['pull_request']['html_url']\
                .encode('utf-8')
