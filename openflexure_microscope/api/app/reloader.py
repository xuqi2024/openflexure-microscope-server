#!/usr/bin/env python
import logging
import threading
import time
from typing import Optional

from flask import Flask
from labthings import LabThing


class AppReloader(object):
    """This class acts as a hook that lets us reload the app.
    
    To obtain the app or the labthing, use the `.app` and `.labthing`
    properties.  These return them, after reloading if required.
    
    This class is callable, and calling it passes the call through
    to the app.  If the reload flag isn't set, it's transparent.
    
    To trigger a reload on the next web request, call `request_reload()`
    and the app and labthing will be deleted and recreated on the next
    HTTP request.
    """

    _app: Optional[Flask] = None
    _labthing: Optional[LabThing] = None
    _to_reload: bool = True
    _lock: Optional[threading.Lock] = None

    def __init__(self, factory_function):
        self.factory_function = factory_function
        self._lock = threading.Lock()
        self._to_reload = True
        self.ensure_app_and_labthing()  # Don't lazy-load

    def ensure_app_and_labthing(self):
        """Reload the app if required by the flag"""
        with self._lock:
            if self._to_reload:
                logging.info("[Re]creating app and labthing...")
                # It is probably good to make sure the app and labthing are released
                # before replacing them.
                self._app, self._labthing = None, None
                time.sleep(1)
                self._app, self._labthing = self.factory_function()
                self._to_reload = False

    def request_reload(self):
        """Trigger a reload on the next request"""
        logging.info("A server reload has been triggered")
        with self._lock:
            self._to_reload = True

    @property
    def labthing(self) -> LabThing:
        """Return the LabThing, after reloading if needed"""
        self.ensure_app_and_labthing()
        assert self._labthing is not None
        return self._labthing

    @property
    def app(self) -> Flask:
        """Return the Flask app, after reloading if needed"""
        self.ensure_app_and_labthing()
        assert self._app is not None
        return self._app

    def __call__(self, environ, start_response):
        """Pass WSGI calls through to the app"""
        return self.app(environ, start_response)  # pylint disable=E1102

    def app_context(self):
        """Pass through app_context() calls to the app"""
        return self.app.app_context()
