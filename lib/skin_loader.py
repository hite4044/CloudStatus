"""
玩家皮肤[获取&渲染]器
"""
import uuid
from base64 import b64decode
from enum import Enum
from io import BytesIO
from json import JSONDecodeError
from os import makedirs, remove
from os.path import isfile

import requests
from PIL import Image, UnidentifiedImageError

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


class SkinLoadWay(Enum):
    MOJANG = 0
    OFFLINE = 1
    LITTLE_SKIN = 2
    FAILED = 64


def get_default_skin_index(uuid_input):
    """
    将UUID转换为默认皮肤索引 (0-17)
    参数：
        uuid_input: 字符串或UUID对象
    返回：
        int: 0到17之间的皮肤索引
    """
    # 将输入转换为UUID对象
    if isinstance(uuid_input, str):
        uuid_obj = uuid.UUID(uuid_input)
    elif isinstance(uuid_input, uuid.UUID):
        uuid_obj = uuid_input
    else:
        raise TypeError("输入必须是UUID字符串或UUID对象")

    # 步骤1-2：异或高64位和低64位
    high64 = (uuid_obj.int >> 64) & 0xFFFFFFFFFFFFFFFF  # 确保取64位
    low64 = uuid_obj.int & 0xFFFFFFFFFFFFFFFF
    intermediate = high64 ^ low64

    # 步骤3-4：异或高32位和低32位
    high32 = (intermediate >> 32) & 0xFFFFFFFF  # 确保取32位
    low32 = intermediate & 0xFFFFFFFF
    hash_code = high32 ^ low32

    # 步骤5：取模确保非负索引 (Python的%已自动处理负数)
    index = hash_code % 18
    return index


def username_to_uuid(username: str) -> uuid.UUID:
    """
    根据Minecraft规则将玩家名转换为离线模式UUID

    参数:
        username (str): 玩家名（不区分大小写）

    返回:
        uuid.UUID: 对应的版本3 UUID

    示例:
        >>> username_to_uuid("Notch")
        UUID('069a79f4-44e9-4726-a5be-fca90e38aaf5')

        >>> username_to_uuid("TEST")
        UUID('a4d6c3c8-0b71-43a7-9d8a-8f3d87fa3b3c')
    """
    # Minecraft要求用户名转换为全小写
    username_clean = username.lower()

    # 使用零命名空间UUID（00000000-0000-0000-0000-000000000000）
    namespace = uuid.UUID(int=0)

    # 生成版本3 UUID（基于MD5哈希）
    return uuid.uuid3(namespace, username_clean)


def get_offline_skin(name: str):
    player_uuid = username_to_uuid(name)
    skin_index = get_default_skin_index(player_uuid)
    with open(DEFAULT_SKINS[skin_index], "rb") as f:
        return Image.open(BytesIO(f.read()))


def request_player_skin_raw(name: str, way: SkinLoadWay) -> tuple[SkinLoadWay, Image.Image | None]:
    logger.debug(f"请求玩家[{name}]头像, 方式: {way}")
    if way == SkinLoadWay.MOJANG:
        resp = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{name}")
        try:
            player_info = resp.json()
        except JSONDecodeError:
            return SkinLoadWay.FAILED, None
        if player_info.get("errorMessage"):
            logger.debug(f"玩家 {name} 不存在")
            return SkinLoadWay.FAILED, None
        if not player_info.get("id"):
            logger.debug(f"玩家 {name} 没有皮肤, 加载默认皮肤")
            return request_player_skin_raw(name, SkinLoadWay.OFFLINE)
        player_uuid = player_info["id"]
        player_profile = requests.get(
            f"https://sessionserver.mojang.com/session/minecraft/profile/{player_uuid}").json()
        skin_info_str = player_profile["properties"][0]["value"]
        skin_info = eval(b64decode(skin_info_str))
        skin_url = skin_info["textures"]["SKIN"]["url"]
        skin_bytes = requests.get(skin_url).content
    elif way == SkinLoadWay.OFFLINE:
        return SkinLoadWay.OFFLINE, get_offline_skin(name)
    elif way == SkinLoadWay.LITTLE_SKIN:
        player_info = requests.get(f"https://littleskin.cn/csl/{name}.json").json()
        if player_info == {}:
            logger.debug(f"玩家 {name} 不存在")
            return SkinLoadWay.FAILED, None
        else:
            if player_info["skins"].get("default"):
                skin_id = player_info["skins"]["default"]
            elif player_info["skins"].get("slim"):
                skin_id = player_info["skins"]["slim"]
            else:
                logger.debug(f"玩家 {name} 没有皮肤, 加载默认皮肤")
                return request_player_skin_raw(name, SkinLoadWay.OFFLINE)
            skin_bytes = requests.get(f"https://littleskin.cn/textures/{skin_id}").content
    else:
        raise ValueError("Invalid skin load way")
    bytes_io = BytesIO(skin_bytes)
    try:
        return way, Image.open(bytes_io).convert("RGBA")
    except UnidentifiedImageError:
        return SkinLoadWay.FAILED, None


def get_player_skin(name: str, way: SkinLoadWay, use_cache: bool = True) -> Image.Image | None:
    makedirs("cache/skin", exist_ok=True)
    logger.debug(f"获取玩家[{name}]皮肤, 方式: {way}, 使用缓存: {use_cache}")

    if isfile(f"cache/skin/{name}_failed(.png"):
        if use_cache:
            return None
        else:
            remove(f"cache/skin/{name}_failed(.png")
    if isfile(f"cache/skin/{name}_offline(.png"):
        if use_cache:
            return get_offline_skin(name)
        else:
            remove(f"cache/skin/{name}_offline(.png")

    if not isfile(f"cache/skin/{name}.png") or not use_cache:
        final_way, skin = request_player_skin_raw(name, way)
        if skin is None:
            with open(f"cache/skin/{name}_failed(.png", "w"):
                pass
            return None
        if final_way == SkinLoadWay.OFFLINE:
            with open(f"cache/skin/{name}_offline(.png", "w"):
                pass
        else:
            skin.save(f"cache/skin/{name}.png")
    else:
        skin = Image.open(f"cache/skin/{name}.png")
    return skin


def render_player_head(skin: Image.Image, target_size: int = 80) -> Image.Image:
    wear_scale = 1.1
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


def get_player_head(name: str, way: SkinLoadWay, size: int = 80, use_cache: bool = True) -> Image.Image:
    makedirs("cache/head", exist_ok=True)
    head_root = f"cache/head/{size}/{name}"
    makedirs(f"cache/head/{size}", exist_ok=True)
    
    skin = get_player_skin(name, way, use_cache)
    if isfile(f"{head_root}_offline(.png"):
        if use_cache:
            return render_player_head(skin, size)
        remove(f"{head_root}_offline(.png")
    if isfile(f"{head_root}_failed(.png"):
        if use_cache:
            return Image.open("assets/default_skin/error_head.png")
        remove(f"{head_root}_failed(.png")
    if skin is None:
        head = Image.open("assets/default_skin/error_head.png")
        head.resize((int(size * 1.1),) * 2, Image.Resampling.BOX)
    elif isfile(f"{head_root}.png") and not use_cache:
        head = Image.open(f"{head_root}.png")
    else:
        head = render_player_head(skin, size)
        if isfile(f"cache/skin/{name}_offline(.png"):
            with open(f"{head_root}_offline(.png", "w"):
                pass
        elif isfile(f"cache/skin/{name}_failed(.png"):
            with open(f"{head_root}_failed(.png", "w"):
                pass
        else:
            head.save(f"{head_root}.png")
    return head
