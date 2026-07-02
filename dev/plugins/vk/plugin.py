from threading import Thread
from .handlers import run_vk_listener

class VKPlugin:
    
    @staticmethod
    def setup(context):
        logger = context.logger_factory("VK", persona="Варя")
        logger.say("Присоединяю ВКонтакте...")
        
        # Запускаем в отдельном потоке, т.к. run_vk_listener — блокирующий while True
        t_vk = Thread(target=run_vk_listener, args=(context,), daemon=True)
        t_vk.start()
        
        logger.say("VK слушатель запущен в фоновом потоке")
