from .handlers import history

async def increase_dice_limit(context):
    # TODO: более информативным сделать этот кусок кода
    await history.tick()
    return None