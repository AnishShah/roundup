from roundup.exceptions import *
from roundup import date

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


valid_events = ('pull_request', 'issue_comment', 'pull_request_review_comment')


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
        if event not in valid_events:
            raise Reject('Unkown X-GitHub-Event %s' % event)
        if event == 'pull_request':
            PullRequest(self.db, self.data)
        elif event == 'issue_comment':
            IssueComment(self.db, self.data)
        elif event == 'pull_request_review_comment':
            PullRequestReviewComment(self.db, self.data)

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

    def handle_comment(self, comment):
        url = self._get_url()
        issue_id = self._get_issue_id_using_url(url)
        if issue_id is not None:
            user_id = self.db.user.lookup("admin")
            messages = self.db.issue.get(issue_id, "messages")
            now = date.Date(".")
            min_date = now - date.Interval("00:30")
            date_range_string = "from " + str(min_date)
            msg_ids = self.db.msg.filter(None, {"is_github_comment": True,
                                                "creation": date_range_string})
            if not bool(msg_ids):
                msg_id = self.db.msg.create(content=comment, author=user_id,
                                            date=now, is_github_comment=True)
                messages.append(msg_id)
                self.db.issue.set(issue_id, messages=messages)
                self.db.commit()

    def _get_issue_id_using_url(self, url):
        pr_id = self.db.github_pullrequest_url.filter(None, {'url': url})
        pr_exists = len(pr_id) == 1
        if pr_exists:
            issue_id = self.db.issue.filter(None, {'github_pullrequest_urls': pr_id[0]})
            if len(issue_id) == 1:
                return issue_id[0]

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
        self.handle_state(url)

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

    def handle_state(self, url):
        url_id = self.db.github_pullrequest_url.filter(None, {'url': url})
        url_exists = len(url_id) == 1
        if url_exists:
            if self.data['pull_request']['merged']:
                state = "merged"
            else:
                state = self.data['pull_request']['state'].encode('utf-8')
            self.db.github_pullrequest_url.set(url_id[0], state=state)
            self.db.commit()


class IssueComment(Event):

    def __init__(self, db, data):
        self.db = db
        self.data = data
        action = self.data['action'].encode('utf-8')
        issue_id = self._get_issue_id()
        url = self._get_url()
        comment = self._get_comment()
        if action == 'created':
            self.handle_create(url, issue_id)
            self.handle_comment(comment)

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

    def _get_comment(self):
        comment_user = self.data['comment']['user']['login'].encode('utf-8')
        comment = self.data['comment']['body'].encode('utf-8')
        url = self.data['comment']['html_url'].encode('utf-8')
        return '%s left a comment on GitHub:\n\n%s\n\n%s' % (comment_user,
                                                           comment, url)


class PullRequestReviewComment(IssueComment):

    def __init__(self, db, data):
        self.db = db
        self.data = data
        action = self.data['action'].encode('utf-8')
        comment = self._get_comment()
        if action == 'created':
            self.handle_comment(comment)

    def _get_url(self):
        return self.data['pull_request']['html_url']
