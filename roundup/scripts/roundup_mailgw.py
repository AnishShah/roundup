# Copyright (c) 2001 Bizar Software Pty Ltd (http://www.bizarsoftware.com.au/)
# This module is free software, and you may redistribute it and/or modify
# under the same terms as Python, so long as this copyright message and
# disclaimer are retained in their original form.
#
# IN NO EVENT SHALL BIZAR SOFTWARE PTY LTD BE LIABLE TO ANY PARTY FOR
# DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES ARISING
# OUT OF THE USE OF THIS CODE, EVEN IF THE AUTHOR HAS BEEN ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# BIZAR SOFTWARE PTY LTD SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING,
# BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE.  THE CODE PROVIDED HEREUNDER IS ON AN "AS IS"
# BASIS, AND THERE IS NO OBLIGATION WHATSOEVER TO PROVIDE MAINTENANCE,
# SUPPORT, UPDATES, ENHANCEMENTS, OR MODIFICATIONS.
# 
# $Id: roundup_mailgw.py,v 1.6.2.1 2003-04-24 04:28:33 richard Exp $

# python version check
from roundup import version_check

import sys, os, re, cStringIO

from roundup.mailgw import Message
from roundup.i18n import _

def usage(args, message=None):
    if message is not None:
        print message
    print _('Usage: %(program)s <instance home> [method]')%{'program': args[0]}
    print _('''

The roundup mail gateway may be called in one of three ways:
 . with an instance home as the only argument,
 . with both an instance home and a mail spool file, or
 . with both an instance home and a pop server account.

PIPE:
 In the first case, the mail gateway reads a single message from the
 standard input and submits the message to the roundup.mailgw module.

UNIX mailbox:
 In the second case, the gateway reads all messages from the mail spool
 file and submits each in turn to the roundup.mailgw module. The file is
 emptied once all messages have been successfully handled. The file is
 specified as:
   mailbox /path/to/mailbox

POP:
 In the third case, the gateway reads all messages from the POP server
 specified and submits each in turn to the roundup.mailgw module. The
 server is specified as:
    pop username:password@server
 The username and password may be omitted:
    pop username@server
    pop server
 are both valid. The username and/or password will be prompted for if
 not supplied on the command-line.
''')
    return 1

def main(args):
    '''Handle the arguments to the program and initialise environment.
    '''
    # figure the instance home
    if len(args) > 1:
        instance_home = args[1]
    else:
        instance_home = os.environ.get('ROUNDUP_INSTANCE', '')
    if not instance_home:
        return usage(args)

    # get the instance
    import roundup.instance
    instance = roundup.instance.open(instance_home)

    # get a mail handler
    db = instance.open('admin')

    # now wrap in try/finally so we always close the database
    try:
        handler = instance.MailGW(instance, db)

        # if there's no more arguments, read a single message from stdin
        if len(args) == 2:
            return handler.do_pipe()

        # otherwise, figure what sort of mail source to handle
        if len(args) < 4:
            return usage(args, _('Error: not enough source specification information'))
        source, specification = args[2:]
        if source == 'mailbox':
            return handler.do_mailbox(specification)
        elif source == 'pop':
            m = re.match(r'((?P<user>[^:]+)(:(?P<pass>.+))?@)?(?P<server>.+)',
                specification)
            if m:
                return handler.do_pop(m.group('server'), m.group('user'),
                    m.group('pass'))
            return usage(args, _('Error: pop specification not valid'))

        return usage(args, _('Error: The source must be either "mailbox" or "pop"'))
    finally:
        db.close()

def run():
    # time out after a minute if we can
    import socket
    if hasattr(socket, 'setdefaulttimeout'):
        socket.setdefaulttimeout(60)
    sys.exit(main(sys.argv))

# call main
if __name__ == '__main__':
    run()

# vim: set filetype=python ts=4 sw=4 et si
