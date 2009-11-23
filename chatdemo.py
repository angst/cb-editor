#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import os.path
import uuid
import hashlib
import time

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/a/text/update", TextUpdateHandler),
            (r"/a/text/listen", TextListenerHandler),
        ]
        settings = dict(
            cookie_secret="43oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        user_json = self.get_secure_cookie("user")
        if not user_json: return None
        return tornado.escape.json_decode(user_json)


class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("index.html", messages=[])


class TextMixin(object):
    waiters = []
    text = { 'body': 'Hello World',
             'sig': hashlib.sha1('Hello World').hexdigest() }
    writer_lock = None
    lock_countdown = 5 # seconds

    def wait_for_update(self, callback, sig=None):
        cls = TextMixin
        if sig != cls.text['sig'] and self.writer() != self.get_secure_cookie('uuid'):
            callback(cls.text)
        else:
            cls.waiters.append(callback)

    def acquire_lock(self, uuid):
        cls = TextMixin
        if self.writer() and self.writer() != uuid:
            return False
        cls.writer_lock = [uuid, time.time()]
        return True

    def writer(self):
        cls = TextMixin
        if cls.writer_lock and (time.time() - cls.writer_lock[1] < cls.lock_countdown):
            return cls.writer_lock[0]

    def update_text(self, body):
        cls = TextMixin
        if self.acquire_lock(self.get_secure_cookie("uuid")):
            cls.text['body'] = body
            cls.text['sig'] = hashlib.sha1(body).hexdigest()
            logging.info("Sending new Text to %r listeners", len(cls.waiters))
            for callback in cls.waiters:
                try:
                    callback(cls.text)
                except:
                    logging.error("Error in waiter callback", exc_info=True)
            cls.waiters = []
        else:
            logging.error("%s didn't have lock" % self.get_secure_cookie("uuid"))

class TextUpdateHandler(BaseHandler, TextMixin):
    def get(self):
        self.update_text(self.get_argument('body'))
        self.write('ok')

    @tornado.web.authenticated
    def post(self):
        self.update_text(self.get_argument('body').encode('utf-8'))
        self.write('ok')

class TextListenerHandler(BaseHandler, TextMixin):
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        sig = self.get_argument("sig", None)
        self.wait_for_update(self.async_callback(self.on_update),
                             sig=sig)

    def on_update(self, body):
        # Closed client connection
        cls = TextMixin
        if self.request.connection.stream.closed():
            return
        if self.writer() != self.get_secure_cookie('uuid'):
            self.finish(body)
        else:
            self.finish('ok')


class AuthLoginHandler(BaseHandler, tornado.auth.GoogleMixin):
    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("openid.mode", None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authenticate_redirect(ax_attrs=["name"])

    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Google auth failed")
        self.set_secure_cookie("user", tornado.escape.json_encode(user))
        self.set_secure_cookie("uuid", str(uuid.uuid4()))
        self.redirect("/")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.write("You are now logged out")


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
