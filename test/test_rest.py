import unittest
import os
import shutil
import errno

from roundup.cgi.exceptions import *
from roundup import password, hyperdb
from roundup.rest import RestfulInstance
from roundup.backends import list_backends
from roundup.cgi import client
import random

import db_test_base

NEEDS_INSTANCE = 1


class TestCase(unittest.TestCase):

    backend = None

    def setUp(self):
        self.dirname = '_test_rest'
        # set up and open a tracker
        self.instance = db_test_base.setupTracker(self.dirname, self.backend)

        # open the database
        self.db = self.instance.open('admin')

        # Get user id (user4 maybe). Used later to get data from db.
        self.joeid = self.db.user.create(
            username='joe',
            password=password.Password('random'),
            address='random@home.org',
            realname='Joe Random',
            roles='User'
        )

        self.db.commit()
        self.db.close()

        env = {
            'PATH_INFO': 'http://localhost/rounduptest/rest/',
            'HTTP_HOST': 'localhost',
            'TRACKER_NAME': 'rounduptest'
        }
        self.dummy_client = client.Client(self.instance, None, env, [], None)
        self.empty_form = cgi.FieldStorage()

    def tearDown(self):
        self.db.close()
        try:
            shutil.rmtree(self.dirname)
        except OSError, error:
            if error.errno not in (errno.ENOENT, errno.ESRCH):
                raise

    def open(self, user='joe'):
        """
        Opens database as given user.
        """
        self.db = self.instance.open(user)

        self.db.tx_Source = 'web'

        self.db.issue.addprop(tx_Source=hyperdb.String())
        self.db.msg.addprop(tx_Source=hyperdb.String())

        self.db.post_init()

        thisdir = os.path.dirname(__file__)
        vars = {}
        execfile(os.path.join(thisdir, "tx_Source_detector.py"), vars)
        vars['init'](self.db)
        self.server = RestfulInstance(self.dummy_client, self.db)

    def testGetSelf(self):
        """
        Retrieve all three users
        obtain data for 'joe'
        """
        self.open()
        # Retrieve all three users.
        results = self.server.get_collection('user', self.empty_form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertEqual(len(results['data']), 3)

        # Obtain data for 'joe'.
        results = self.server.get_element('user', self.joeid, self.empty_form)
        results = results['data']
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertEqual(results['attributes']['username'], 'joe')
        self.assertEqual(results['attributes']['realname'], 'Joe Random')

        # Obtain data for 'joe'.
        results = self.server.get_attribute(
            'user', self.joeid, 'username', self.empty_form
        )
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertEqual(results['data']['data'], 'joe')

    def testGetAdmin(self):
        """
        Read admin data.
        """
        self.open()
        results = self.server.get_element('user', '1', self.empty_form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertFalse(results['data']['attributes'].has_key('openids'))
        self.assertFalse(results['data']['attributes'].has_key('password'))

    def testGetSelfAttribute(self):
        """
        Read admin data.
        """
        self.open()
        results = self.server.get_attribute('user', self.joeid, 'password', self.empty_form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertIsNotNone(results['data']['data'])

    def testGetAdminAttribute(self):
        """
        Read admin data.
        """
        self.open()
        # Retrieve all three users.
        results = self.server.get_attribute('user', '1', 'password', self.empty_form)
        self.assertEqual(self.dummy_client.response_code, 403)

    def testGetAnonymous(self):
        """
        Anonymous should not get users.
        """
        self.open('anonymous')
        results = self.server.get_collection('user', self.empty_form)
        self.assertEqual(self.dummy_client.response_code, 403)

    def testFilter(self):
        """
        Retrieve all three users
        obtain data for 'joe'
        """
        self.open()
        # create sample data
        try:
            self.db.status.create(name='open')
        except ValueError:
            pass
        try:
            self.db.status.create(name='closed')
        except ValueError:
            pass
        try:
            self.db.priority.create(name='normal')
        except ValueError:
            pass
        try:
            self.db.priority.create(name='critical')
        except ValueError:
            pass
        self.db.issue.create(
            title='foo4',
            status=self.db.status.lookup('closed'),
            priority=self.db.priority.lookup('critical')
        )
        self.db.issue.create(
            title='foo1',
            status=self.db.status.lookup('open'),
            priority=self.db.priority.lookup('normal')
        )
        issue_open_norm = self.db.issue.create(
            title='foo2',
            status=self.db.status.lookup('open'),
            priority=self.db.priority.lookup('normal')
        )
        issue_closed_norm = self.db.issue.create(
            title='foo3',
            status=self.db.status.lookup('closed'),
            priority=self.db.priority.lookup('normal')
        )
        issue_closed_crit = self.db.issue.create(
            title='foo4',
            status=self.db.status.lookup('closed'),
            priority=self.db.priority.lookup('critical')
        )
        issue_open_crit = self.db.issue.create(
            title='foo5',
            status=self.db.status.lookup('open'),
            priority=self.db.priority.lookup('critical')
        )
        base_path = self.dummy_client.env['PATH_INFO'] + 'data/issue/'

        # Retrieve all issue status=open
        form = cgi.FieldStorage()
        form.list = [
            cgi.MiniFieldStorage('where_status', 'open')
        ]
        results = self.server.get_collection('issue', form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertIn(get_obj(base_path, issue_open_norm), results['data'])
        self.assertIn(get_obj(base_path, issue_open_crit), results['data'])
        self.assertNotIn(
            get_obj(base_path, issue_closed_norm), results['data']
        )

        # Retrieve all issue status=closed and priority=critical
        form = cgi.FieldStorage()
        form.list = [
            cgi.MiniFieldStorage('where_status', 'closed'),
            cgi.MiniFieldStorage('where_priority', 'critical')
        ]
        results = self.server.get_collection('issue', form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertIn(get_obj(base_path, issue_closed_crit), results['data'])
        self.assertNotIn(get_obj(base_path, issue_open_crit), results['data'])
        self.assertNotIn(
            get_obj(base_path, issue_closed_norm), results['data']
        )

        # Retrieve all issue status=closed and priority=normal,critical
        form = cgi.FieldStorage()
        form.list = [
            cgi.MiniFieldStorage('where_status', 'closed'),
            cgi.MiniFieldStorage('where_priority', 'normal,critical')
        ]
        results = self.server.get_collection('issue', form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertIn(get_obj(base_path, issue_closed_crit), results['data'])
        self.assertIn(get_obj(base_path, issue_closed_norm), results['data'])
        self.assertNotIn(get_obj(base_path, issue_open_crit), results['data'])
        self.assertNotIn(get_obj(base_path, issue_open_norm), results['data'])

    def testPagination(self):
        """
        Retrieve all three users
        obtain data for 'joe'
        """
        self.open()
        # create sample data
        for i in range(0, random.randint(5, 10)):
            self.db.issue.create(title='foo' + str(i))

        # Retrieving all the issues
        results = self.server.get_collection('issue', self.empty_form)
        self.assertEqual(self.dummy_client.response_code, 200)
        total_length = len(results['data'])

        # Pagination will be 70% of the total result
        page_size = total_length * 70 // 100
        page_zero_expected = page_size
        page_one_expected = total_length - page_zero_expected

        # Retrieve page 0
        form = cgi.FieldStorage()
        form.list = [
            cgi.MiniFieldStorage('page_size', page_size),
            cgi.MiniFieldStorage('page_index', 0)
        ]
        results = self.server.get_collection('issue', form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertEqual(len(results['data']), page_zero_expected)

        # Retrieve page 1
        form = cgi.FieldStorage()
        form.list = [
            cgi.MiniFieldStorage('page_size', page_size),
            cgi.MiniFieldStorage('page_index', 1)
        ]
        results = self.server.get_collection('issue', form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertEqual(len(results['data']), page_one_expected)

        # Retrieve page 2
        form = cgi.FieldStorage()
        form.list = [
            cgi.MiniFieldStorage('page_size', page_size),
            cgi.MiniFieldStorage('page_index', 2)
        ]
        results = self.server.get_collection('issue', form)
        self.assertEqual(self.dummy_client.response_code, 200)
        self.assertEqual(len(results['data']), 0)


def get_obj(path, id):
    return {
        'id': id,
        'link': path + id
    }


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
