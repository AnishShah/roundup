# Copyright (c) 2002 ekit.com Inc (http://www.ekit-inc.com/)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# $Id: test_locking.py,v 1.1 2002-04-15 23:25:15 richard Exp $

import os, unittest, tempfile

from roundup.backends.locking import acquire_lock, release_lock

class LockingTest(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp()
        open(self.path, 'w').write('hi\n')

    def test_basics(self):
        f = acquire_lock(self.path)
        try:
            acquire_lock(self.path, block=0)
        except:
            pass
        else:
            raise AssertionError, 'no exception'
        release_lock(f)
        f = acquire_lock(self.path)
        release_lock(f)

    def tearDown(self):
        os.remove(self.path)

def suite():
    return unittest.makeSuite(LockingTest)


#
# $Log: not supported by cvs2svn $
#
#
# vim: set filetype=python ts=4 sw=4 et si
