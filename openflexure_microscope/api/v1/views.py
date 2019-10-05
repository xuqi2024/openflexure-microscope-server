from flask.views import MethodView


class MicroscopeView(MethodView):
    """
    Create a generic MethodView with a globally available
    microscope object passed as an argument.
    """

    def __init__(self, microscope, **kwargs):

        self.microscope = microscope

        MethodView.__init__(self, **kwargs)


class MicroscopeViewPlugin(MicroscopeView):
    """
    Create a generic MethodView with a globally available
    microscope object passed as an argument, and a plugin
    reference stored in 'self'. Initially None.
    """

    def __init__(self, microscope, plugin=None, **kwargs):

        self.plugin = plugin

        MicroscopeView.__init__(self, microscope=microscope, **kwargs)
