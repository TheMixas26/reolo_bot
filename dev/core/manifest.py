from __future__ import annotations

from dataclasses import dataclass, field

from varibles import TEXT

@dataclass(frozen=True)
class PluginManifest:
    name: str
    persona: str
    summary: str

    # Различные теги для группировки/поиска, например: "moderation", "games", "fun" и т.д.
    tags: tuple[str, ...] = field(default_factory=tuple)

    # Пока что всего лишь предупреждения о том, что плагин делает и куда лезет.
    # Примеры: "меняет баланс", "банит людей", "работает в чате" и т.д.
    touches: tuple[str, ...] = field(default_factory=tuple)

    # Уровень прав по умолчанию для команд плагина, если сам
    # плагин не переопределяет его точечно через core/permissions.py.
    permission: str = "public"

    # True - плагину нужна монополия на чат, пока идёт какая-нибудь сессия.
    # Например, мафия, крокодил, камень-ножницы-бумага.
    monopoly: bool = False


REGISTRY: list[PluginManifest] = []


def register_manifest(manifest: PluginManifest) -> PluginManifest:
    """Регистрируем манифест в общем реестре"""
    REGISTRY.append(manifest)
    return manifest


async def render_summary() -> str:
    """Собирает текст для команды /plugins"""
    if not REGISTRY:
        return TEXT("no_plugins_manifests")

    paragraphs = []
    for plugin in REGISTRY:
        # TODO: core texts.json
        lines = [f"<b>{plugin.name}</b> ({plugin.persona}) — {plugin.summary}"]
        if plugin.tags:
            lines.append("Теги: " + ", ".join(plugin.tags))

        if plugin.monopoly:
            lines.append("[!] Занимает чат монопольно на время сессии")

        for touch in plugin.touches:
            lines.append(f"• {touch}")

        paragraphs.append("\n".join(lines))

    return "\n\n".join(paragraphs)