from .handlers import register_handlers

class CorePlugin:
    @staticmethod
    def register_handlers(context):
        register_handlers(context)

    @staticmethod
    def setup(context):
        CorePlugin.register_handlers(context)
