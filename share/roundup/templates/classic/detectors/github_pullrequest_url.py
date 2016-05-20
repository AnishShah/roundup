# Auditor for GitHub URLs
# Check if it is a valid GitHub Pull Request URL and extract PR number
import re
import urlparse


def validate_github_url(db, cl, nodeid, newvalues):
    url = newvalues.get('url', '')
    parsed_url = urlparse.urlparse(url)
    if parsed_url.scheme not in ('http', 'https'):
        raise ValueError("Invalid URL scheme in GitHub Pull Request URL")
    if 'github.com' not in parsed_url.netloc or 'pull' not in parsed_url.path:
        raise ValueError("Invalid GitHub Pull Request URL")
    newvalues['url'] = (parsed_url.scheme + "://" + parsed_url.netloc +
                        parsed_url.path)
    regex = re.match(".*/pull/(\d+)", newvalues['url'])
    if regex and len(regex.groups()) == 1:
        pullrequest_number = regex.groups()[0]
        try:
            github_url_id = db.github_pullrequest_url.lookup(pullrequest_number)
            raise ValueError("GitHub Pull Request URL already added to an issue")
        except KeyError:
            newvalues['pullrequest_number'] = pullrequest_number
    else:
        raise ValueError("Invalid GitHub Pull Request URL")


def init(db):
    db.github_pullrequest_url.audit('create', validate_github_url)
    db.github_pullrequest_url.audit('set', validate_github_url)
