from .handlers import register_handlers
from .jobs import send_template_message
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="NAME",
        persona="PERSONA",
        summary="SUMMARY",
        tags=("tag1", "tag2",),
        touches=(
            "smth1",
            "smth2",
            # smth else...
        ),
        permission="public",
        monopoly="True OR False",
    ))

class TemplatePlugin:
    # TODO: засунуть это куда-нибудь, оно не используется сейчас
    manifest=MANIFEST
    
    @staticmethod
    def register_handlers(context):
        context.include_router("predlojka", register_handlers(context))

    @staticmethod
    def register_jobs(context):
        context.scheduler.add_job(
            send_template_message,
            'interval',
            minutes=5,
            args=(context,),
        )

    @staticmethod
    def setup(context):
        context.ensure_bot("predlojka", display_name="ПРЕДЛОЖКА")
        logger = context.logger_factory("template", persona="Шаблон")
        logger.say("Шаблон плагина активирован")
        TemplatePlugin.register_jobs(context)
        TemplatePlugin.register_handlers(context)
