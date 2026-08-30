from .handlers import register_handlers

class CorePlugin:
    @staticmethod
    def register_handlers(context):
        context.include_router("predlojka", register_handlers(context))

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        CorePlugin.register_handlers(context)
