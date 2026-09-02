from threading import Thread
from .handlers import run_vk_listener
from core.manifest import PluginManifest, register_manifest

MANIFEST = register_manifest(PluginManifest(
        name="VK",
        persona="Варя",
        summary="Работа с ВК",
        tags=("moderation",),
        touches=(
            "основной хендлер предложки",
            "пересылка постов",
            # smth else...
        ),
        permission="public",
        monopoly=False,
    ))

class VKPlugin:
    
    @staticmethod
    def setup(context):
        logger = context.logger_factory("VK", persona="Варя")
        logger.say("Присоединяю ВКонтакте...")
        
        # Запускаем в отдельном потоке, т.к. run_vk_listener — блокирующий while True
        t_vk = Thread(target=run_vk_listener, args=(context,), daemon=True)
        t_vk.start()
        
        logger.say("VK слушатель запущен в фоновом потоке")
