"""
玩家皮肤[获取&渲染]器
"""
import json
import typing
import uuid
from base64 import b64decode
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from json import JSONDecodeError
from os import makedirs
from os.path import isfile
from threading import Thread, Lock, Event
from typing import Callable, Any

import requests
from PIL import Image, UnidentifiedImageError

from lib.config import config, SkinLoadWay
from lib.data import Player
from lib.log import logger

headers = {
    "User-Agent": "CloudStatus@github <LoadPlayerHead> lib/skin_loader.py:request_player_head_raw",
    "Content-Type": "application/json"
}

SKIN_NAMES = ["alex", "ari", "efe", "kai", "makena", "noor", "steve", "sunny", "zuri"]

DEFAULT_SKINS: list[str] = [
    *[f"assets/default_skin/slim/{n}.png" for n in SKIN_NAMES],
    *[f"assets/default_skin/wide/{n}.png" for n in SKIN_NAMES]
]


class SkinServer:
    def __init__(self, root: str, texture_path: str):
        self.root: str = root
        self.texture_path = texture_path
        self.profile_server: str = f"{root}"
        self.texture_server: str = f"{root}/textures"


SKIN_SERVER_PRE_DEF = {
    SkinLoadWay.LITTLE_SKIN: SkinServer("https://littleskin.cn/csl", "skins")
}


class ContentStatus(Enum):
    NOT_LOADED = 0  # 没有加载
    CACHED = 1  # 已缓存
    OFFLINE = 2  # 使用离线皮肤
    FAILED = 3  # 失败


class SkinLoadStatus(Enum):
    SUCCESS = 0
    FAILED = 1
    OFFLINE_SKIN = 2


class PlayerContentType(Enum):
    SKIN = 0
    HEAD = 1


@dataclass
class ContentLoadData:
    """内容加载数据 (参数)"""
    player: Player
    type_: PlayerContentType
    use_cache: bool = True
    size: int = 80
    wear_scale: float = 1.1


@dataclass
class SkinRequestData:
    """皮肤请求数据 (参数)"""
    way: SkinLoadWay
    skin_server: str = None
    textures_server: str = None


class SkinLoadData(ContentLoadData):
    """皮肤加载数据 (参数)"""

    def __init__(self, player: Player, use_cache: bool = True):
        super().__init__(player, PlayerContentType.SKIN, use_cache)


class HeadLoadData(ContentLoadData):
    """头像加载数据 (参数)"""

    def __init__(self, player: Player, size: int = 80, wear_scale: float = 1.1, use_cache: bool = True):
        super().__init__(player, PlayerContentType.HEAD, use_cache, size, wear_scale)


@dataclass
class PlayerContentInfo:
    """一个玩家的内容状态&缓存"""
    name: Player
    skin_status: ContentStatus = ContentStatus.NOT_LOADED
    head_status: dict[int, ContentStatus] = field(default_factory=dict)
    skin: Image.Image | None = None
    head: dict[int, Image.Image] = field(default_factory=dict)


def get_default_skin_index(uuid_input):
    """
    将UUID转换为默认皮肤索引 (0-17)
    Args:
        uuid_input: 字符串或UUID对象
    Returns:
        int: 0到17之间的皮肤索引
    """
    # 将输入转换为UUID对象
    if isinstance(uuid_input, str):
        uuid_obj = uuid.UUID(uuid_input)
    elif isinstance(uuid_input, uuid.UUID):
        uuid_obj = uuid_input
    else:
        raise TypeError("输入必须是UUID字符串或UUID对象")

    # 异或高64位和低64位
    high64 = (uuid_obj.int >> 64) & 0xFFFFFFFFFFFFFFFF  # 确保取64位
    low64 = uuid_obj.int & 0xFFFFFFFFFFFFFFFF
    intermediate = high64 ^ low64

    # 异或高32位和低32位
    high32 = (intermediate >> 32) & 0xFFFFFFFF  # 确保取32位
    low32 = intermediate & 0xFFFFFFFF
    hash_code = high32 ^ low32

    # 取模确保非负索引 (Python的%已自动处理负数)
    index = hash_code % 18
    return index


def username_to_uuid(username: str) -> uuid.UUID:
    """
    根据Minecraft规则将玩家名转换为离线模式UUID
    Args:
        username (str): 玩家名 (不区分大小写)
    Returns:
        uuid.UUID: 对应的版本3 UUID
    """
    # Minecraft要求用户名转换为全小写
    username_clean = username.lower()

    # 使用零命名空间UUID (00000000-0000-0000-0000-000000000000)
    namespace = uuid.UUID(int=0)

    # 生成版本3 UUID (基于MD5哈希)
    return uuid.uuid3(namespace, username_clean)


def get_offline_skin(name: str):
    """获取离线皮肤"""
    player_uuid = username_to_uuid(name)
    skin_index = get_default_skin_index(player_uuid)
    with open(DEFAULT_SKINS[skin_index], "rb") as f:
        return Image.open(BytesIO(f.read()))


def render_player_head(skin: Image.Image, target_size: int = 80, wear_scale: float = 1.1) -> Image.Image:
    """渲染玩家皮肤"""
    px_size = int(skin.width / 64)
    if px_size != 1:
        wear_scale = 1
    final_size = int(target_size * wear_scale)
    pad = (final_size - target_size) // 2

    head = skin.crop((8 * px_size, 8 * px_size, (8 + 8) * px_size, (8 + 8) * px_size))  # 获取原始头颅部分
    head_wear = skin.crop((40 * px_size, 8 * px_size, (40 + 8) * px_size, (8 + 8) * px_size))  # 获取原始头颅装饰部分

    base_canvas = Image.new("RGBA",  # 新建空白基础画布, 8(基础大小) *px_size(头颅大小) * wear_scale(全头大小)
                            (final_size, final_size),
                            (0, 0, 0, 0))
    scaled_head = head.resize((target_size, target_size), Image.Resampling.BOX)
    base_canvas.paste(scaled_head, (pad, pad))
    scaled_wear = head_wear.resize((final_size, final_size), Image.Resampling.BOX)
    base_canvas.paste(scaled_wear, (0, 0), mask=scaled_wear)
    return base_canvas


def request_skin_offline(player: Player) -> tuple[SkinLoadStatus, Image.Image]:
    return SkinLoadStatus.OFFLINE_SKIN, get_offline_skin(player.name)


def request_skin_mojang(player: Player) -> tuple[SkinLoadStatus, Image.Image | None]:
    try:
        resp = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{player.name}")
        player_info = resp.json()
    except ConnectionError as e:
        logger.error(f"获取皮肤失败 -> UUID信息服务器连接错误 [{player.name}] -> {e}")
        return SkinLoadStatus.FAILED, None
    except JSONDecodeError as e:
        logger.error(f"获取皮肤失败 -> UUID信息Json异常 [{player.name}] -> {e}")
        return SkinLoadStatus.FAILED, None
    if player_info.get("errorMessage") or (not player_info.get("id")):
        logger.debug(f"玩家 {player.name} 没有皮肤, 加载默认皮肤")
        return request_skin_offline(player)
    try:
        resp = requests.get(
            f"https://sessionserver.mojang.com/session/minecraft/profile/{player_info['id']}")
        profile = resp.json()
    except ConnectionError as e:
        logger.error(f"获取皮肤失败 -> 个人信息服务器连接错误 [{player.name}] -> {e}")
        return SkinLoadStatus.FAILED, None
    except JSONDecodeError as e:
        logger.error(f"获取皮肤失败 -> 个人信息Json异常 [{player.name}] -> {e}")
        return SkinLoadStatus.FAILED, None
    try:
        skin_info_str = profile["properties"][0]["value"]
        skin_info = eval(b64decode(skin_info_str))
        skin_url = skin_info["textures"]["SKIN"]["url"]

        image_bytes = requests.get(skin_url).content
        image_io = BytesIO(image_bytes)
        return SkinLoadStatus.SUCCESS, Image.open(image_io)
    except ConnectionError as e:
        logger.error(f"获取皮肤失败 -> 贴图服务器连接错误 [{player.name}] -> {e}")
        return SkinLoadStatus.FAILED, None
    except KeyError as e:
        logger.error(f"获取皮肤失败 -> 皮肤信息Json损坏 [{player.name}] -> {e}")
        return SkinLoadStatus.FAILED, None


def request_skin_custom(player: Player, req_data: SkinRequestData) -> tuple[SkinLoadStatus, Image.Image | None]:
    if req_data.way == SkinLoadWay.CUSTOM_SERVER:
        server = SkinServer(config.custom_skin_server, config.custom_skin_root)
    else:
        server = SKIN_SERVER_PRE_DEF[req_data.way]
    try:
        resp = requests.get(f"{server.profile_server}/{player.name}.json")
        skin_info = resp.json()
        skin_id = None
        for assets_name in skin_info[server.texture_path].keys():
            if assets_name == "default":
                skin_id = skin_info[server.texture_path][assets_name]
            elif assets_name == "slim":
                skin_id = skin_info[server.texture_path][assets_name]
            else:
                continue
            break
        if skin_id is None:
            return SkinLoadStatus.OFFLINE_SKIN, get_offline_skin(player.name)
    except ConnectionError:
        return SkinLoadStatus.FAILED, None
    except JSONDecodeError:
        return SkinLoadStatus.FAILED, None
    except KeyError:
        return SkinLoadStatus.FAILED, None
    skin_url = f"{server.texture_server}/{skin_id}"
    try:
        image_io = BytesIO(requests.get(skin_url).content)
        return SkinLoadStatus.SUCCESS, Image.open(image_io).convert("RGBA")
    except ConnectionError:
        return SkinLoadStatus.FAILED, None
    except UnidentifiedImageError:
        return SkinLoadStatus.FAILED, None


def request_skin(player: Player, req_data: SkinRequestData = None) -> tuple[SkinLoadStatus, Image.Image | None]:
    logger.debug(f"请求玩家皮肤 -> 玩家: {player.name}, 方式: {req_data.way}")
    if req_data.way == SkinLoadWay.MOJANG:
        return request_skin_mojang(player)
    elif req_data.way == SkinLoadWay.OFFLINE:
        return request_skin_offline(player)
    else:
        return request_skin_custom(player, req_data)


class PlayerContentManager:
    def __init__(self):
        self.contents: dict[Player, PlayerContentInfo] = {}
        self.task_lock = Lock()
        self.active_tasks: list[tuple[Player, Callable, tuple[Any, ...]]] = []
        self.loader_thread: Thread = Thread(target=self.skin_loader, daemon=True)
        self.content_write_counter = 0
        self.load_cache()

    def load_cache(self):
        """加载皮肤缓存"""
        logger.info("加载皮肤缓存状态...")
        makedirs("cache", exist_ok=True)
        if not isfile(r"cache\contents.json"):
            return
        with open(r"cache\contents.json", "r") as f:
            data = json.load(f)
        enum_values = [member.value for name, member in ContentStatus.__members__.items()]
        for player_name, status_value in data.items():
            player = Player(player_name)
            if status_value not in enum_values:
                continue
            self.contents[player] = PlayerContentInfo(player, ContentStatus(status_value))

    def save_cache(self):
        """保存皮肤缓存"""
        logger.info("保存皮肤缓存状态...")
        makedirs("cache", exist_ok=True)
        data: dict[str, int] = {}
        # 将皮肤缓存状态转化为一对一的字典
        for player, info in self.contents.items():
            data[player.name] = info.skin_status.value
        try:
            with open(r"cache\contents.json", "w") as f:
                json.dump(data, typing.cast(typing.Any, f))
        except IOError as e:
            logger.error(f"保存皮肤缓存状态失败 -> {e}")

    def add_task(self, player: Player, callback: Callable, *func_args):
        """
        添加一个皮肤加载任务
        Args:
            player: 玩家
            callback: 回调函数
            func_args: 回调函数的参数
        """
        with self.task_lock:
            self.active_tasks.append((player, callback, func_args))
            if not self.loader_thread.is_alive():
                self.loader_thread = Thread(target=self.skin_loader, daemon=True)
                self.loader_thread.start()

    def skin_loader(self):
        """皮肤加载线程函数"""
        while True:
            with self.task_lock:
                if not self.active_tasks:
                    return
                task = self.active_tasks.pop(0)
                player, callback, func_args = task
            req_data = SkinRequestData(config.skin_load_way, config.custom_skin_server, config.custom_skin_root)
            status, skin = request_skin(player, req_data)
            if status == SkinLoadStatus.OFFLINE_SKIN:
                skin_status = ContentStatus.OFFLINE
            elif status == SkinLoadStatus.FAILED:
                skin_status = ContentStatus.FAILED
            else:
                skin_status = ContentStatus.CACHED
                makedirs("cache\\skin", exist_ok=True)
                skin.save(f"cache\\skin\\{player.name}.png")
                self.get_content(player).skin = skin
            self.get_content(player).skin_status = skin_status
            if self.content_write_counter > config.player_content_cache_inv:
                self.save_cache()
            callback(*func_args)

    def get_content(self, player: Player):
        """获取玩家的内容信息"""
        # 如果玩家不在映射中, 则初始化其内容信息
        if player not in self.contents:
            self.contents[player] = PlayerContentInfo(player)
        return self.contents[player]

    def get_player_skin(self, data: SkinLoadData) -> tuple[ContentStatus, Image.Image | None]:
        """
        获取玩家皮肤
        Args:
            data (SkinLoadData): 包含玩家信息和缓存策略的参数对象      
        Returns:
            tuple[ContentStatus, Image.Image | None]:
                第一项为皮肤加载状态枚举值, 第二项为皮肤图像对象（若未加载成功则为None）
        """
        content = self.get_content(data.player)
        if content.skin_status == ContentStatus.NOT_LOADED or (not data.use_cache):
            # 添加加载任务并等待任务完成
            event = Event()

            def callback():
                event.set()

            self.add_task(data.player, callback)
            event.wait()
        elif data.use_cache and content.skin_status == ContentStatus.CACHED:
            # 从缓存路径加载皮肤图像
            if not content.skin:
                skin = Image.open(rf"cache\skin\{data.player.name}.png")
                content.skin = skin
        elif content.skin_status == ContentStatus.OFFLINE:
            # 处理离线皮肤情况
            skin = get_offline_skin(data.player.name)
            return ContentStatus.OFFLINE, skin
        return content.skin_status, content.skin

    def get_player_head(self, data: HeadLoadData) -> tuple[ContentStatus, Image.Image | None]:
        """
        获取玩家头像
        Args:
            data (HeadLoadData): 包含玩家信息、缓存设置和头像尺寸等数据
        Returns:
            tuple[ContentStatus, Image.Image | None]:
                第一个项为头像状态 (如缓存成功、失败等), 第二个元素为渲染后的头像图像或None
        """
        content = self.get_content(data.player)

        # 如果头像未缓存, 则开始获取皮肤并渲染头像
        if content.head_status.get(data.size) not in [ContentStatus.CACHED, ContentStatus.OFFLINE] or (
                not data.use_cache):
            # 获取皮肤
            skin_data = SkinLoadData(data.player, data.use_cache)
            skin_status, skin = self.get_player_skin(skin_data)
            if skin_status == ContentStatus.FAILED:  # 如果皮肤获取失败, 则返回错误头像
                return ContentStatus.FAILED, Image.open("assets/default_skin/error_head.png")
            elif skin_status == ContentStatus.OFFLINE:  # 如果是离线皮肤, 则使用离线皮肤
                skin = get_offline_skin(data.player.name)

            # 渲染并缓存头像
            head = render_player_head(skin, data.size, data.wear_scale)
            content.head[data.size] = head
            content.head_status[data.size] = skin_status
            return skin_status, head

        # 返回缓存的头像及状态
        return content.head_status[data.size], content.head[data.size]

    def add_head_task(self, data: HeadLoadData, callback: Callable):
        def thread_func():
            callback(*self.get_player_head(data))

        Thread(target=thread_func, daemon=True).start()


skin_mgr = PlayerContentManager()
if __name__ == "__main__":
    print(skin_mgr.get_player_head(HeadLoadData(Player("asdgfasdfsadf"))))
    print(skin_mgr.get_player_head(HeadLoadData(Player("asdgfasdfsadf"))))
    skin_mgr.save_cache()
