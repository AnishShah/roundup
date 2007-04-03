#
# Copyright (C) 2007 Stefan Seefeld
# All rights reserved.
# For license terms see the file COPYING.txt.
#

import base64
import roundup.instance
from roundup import hyperdb
from roundup.cgi.exceptions import *
from roundup.admin import UsageError
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler

class RoundupRequestHandler(SimpleXMLRPCRequestHandler):
    """A SimpleXMLRPCRequestHandler with support for basic
    HTTP Authentication."""

    def do_POST(self):
        """Extract username and password from authorization header."""

        # Try to extract username and password from HTTP Authentication.
        self.username = None
        self.password = None
        authorization = self.headers.get('authorization', ' ')
        scheme, challenge = authorization.split(' ', 1)

        if scheme.lower() == 'basic':
            decoded = base64.decodestring(challenge)
            self.username, self.password = decoded.split(':')

        SimpleXMLRPCRequestHandler.do_POST(self)

    def _dispatch(self, method, params):
        """Inject username and password into function arguments."""

        # Add username and password to function arguments
        params = [self.username, self.password] + list(params)
        return self.server._dispatch(method, params)


class RoundupRequest:
    """Little helper class to handle common per-request tasks such
    as authentication and login."""

    def __init__(self, tracker, username, password):
        """Open the database for the given tracker, using the given
        username and password."""

        self.tracker = tracker
        self.db = self.tracker.open('admin')
        try:
            userid = self.db.user.lookup(username)
        except KeyError: # No such user
            raise Unauthorised, 'Invalid user.'
        stored = self.db.user.get(userid, 'password')
        if stored != password: # Wrong password
            raise Unauthorised, 'Invalid user.'
        self.db.setCurrentUser(username)
        
    def close(self):
        """Close the database, after committing any changes, if needed."""

        if getattr(self, 'db'):
            try:
                if self.db.transactions:
                    self.db.commit()
            finally:
                self.db.close()


    def get_class(self, classname):
        """Return the class for the given classname."""

        try:
            return self.db.getclass(classname)
        except KeyError:
            raise UsageError, 'no such class "%s"'%classname

    def props_from_args(self, cl, args):
        """Construct a list of properties from the given arguments,
        and return them after validation."""

        props = {}
        for arg in args:
            if arg.find('=') == -1:
                raise UsageError, 'argument "%s" not propname=value'%arg
            l = arg.split('=')
            if len(l) < 2:
                raise UsageError, 'argument "%s" not propname=value'%arg
            key, value = l[0], '='.join(l[1:])
            if value:
                try:
                    props[key] = hyperdb.rawToHyperdb(self.db, cl, None,
                                                      key, value)
                except hyperdb.HyperdbValueError, message:
                    raise UsageError, message
            else:
                props[key] = None

        return props


#The server object
class RoundupServer:
    """The RoundupServer provides the interface accessible through
    the Python XMLRPC mapping. All methods take an additional username
    and password argument so each request can be authenticated."""

    def __init__(self, tracker, verbose = False):
        self.tracker = roundup.instance.open(tracker)
        self.verbose = verbose

    def list(self, username, password, classname, propname = None):

        r = RoundupRequest(self.tracker, username, password)
        cl = r.get_class(classname)
        if not propname:
            propname = cl.labelprop()
        result = [cl.get(id, propname) for id in cl.list()]
        r.close()
        return result

    def display(self, username, password, designator, *properties):

        r = RoundupRequest(self.tracker, username, password)
        classname, nodeid = hyperdb.splitDesignator(designator)
        cl = r.get_class(classname)
        props = properties and list(properties) or cl.properties.keys()
        props.sort()
        result = [(property, cl.get(nodeid, property)) for property in props]
        r.close()
        return dict(result)

    def create(self, username, password, classname, *args):

        r = RoundupRequest(self.tracker, username, password)
        cl = r.get_class(classname)

        # convert types
        props = r.props_from_args(cl, args)

        # check for the key property
        key = cl.getkey()
        if key and not props.has_key(key):
            raise UsageError, 'you must provide the "%s" property.'%key

        # do the actual create
        try:
            result = cl.create(**props)
        except (TypeError, IndexError, ValueError), message:
            raise UsageError, message
        finally:
            r.close()
        return result

    def set(self, username, password, designator, *args):

        r = RoundupRequest(self.tracker, username, password)
        classname, itemid = hyperdb.splitDesignator(designator)
        cl = r.get_class(classname)

        # convert types
        props = r.props_from_args(cl, args)
        try:
            cl.set(itemid, **props)
        except (TypeError, IndexError, ValueError), message:
            raise UsageError, message
        finally:
            r.close()

