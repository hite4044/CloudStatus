"""
玩家皮肤[获取&渲染]器
"""
import uuid
from base64 import b64decode
from enum import Enum
from io import BytesIO

import requests
from PIL import Image

from lib.log import logger

headers = {
    "User-Agent": "CloudStatus@github LoadPlayerHead lib/skin_loader.py:request_player_head",
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


def request_player_skin(name: str, way: SkinLoadWay = SkinLoadWay.LITTLE_SKIN) -> Image.Image:
    logger.debug(f"请求玩家[{name}]头像, 方式: {way}")
    if way == SkinLoadWay.MOJANG:
        player_info = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{name}").json()
        player_uuid = player_info["id"]
        player_profile = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{player_uuid}").json()
        skin_info_str = player_profile["properties"][0]["value"]
        skin_info = eval(b64decode(skin_info_str))
        skin_url = skin_info["textures"]["SKIN"]["url"]
        skin_bytes = requests.get(skin_url).content
    elif way == SkinLoadWay.OFFLINE:
        player_uuid = username_to_uuid(name)
        skin_index = get_default_skin_index(player_uuid)
        with open(DEFAULT_SKINS[skin_index], "rb") as f:
            skin_bytes = f.read()
    elif way == SkinLoadWay.LITTLE_SKIN:
        player_info = requests.get(f"https://littleskin.cn/csl/{name}.json").json()
        if player_info == {}:
            skin_bytes = open("assets/default_skin/skin_lost.png", "rb").read()
        else:
            if player_info["skins"].get("default"):
                skin_id = player_info["skins"]["default"]
            elif player_info["skins"].get("slim"):
                skin_id = player_info["skins"]["slim"]
            else:
                logger.debug(f"玩家 {name} 没有皮肤, 加载默认皮肤")
                return request_player_skin(name, SkinLoadWay.OFFLINE)
            skin_bytes = requests.get(f"https://littleskin.cn/textures/{skin_id}").content
    else:
        raise ValueError("Invalid skin load way")
    bytes_io = BytesIO(skin_bytes)
    return Image.open(bytes_io).convert("RGBA")


def render_player_head(skin: Image.Image, target_size: int = 64) -> Image.Image:
    px_mutil = 1.1
    px_size = int(skin.width / 64)
    head = skin.crop((8 * px_size, 8 * px_size, (8 + 8) * px_size, (8 + 8) * px_size))
    head_wear = skin.crop((40 * px_size, 8 * px_size, (40 + 8) * px_size, (8 + 8) * px_size))
    render_scale = int(target_size / 8)
    if px_size != 1:
        px_mutil = 1

    base_canvas = Image.new("RGBA",  # 新建空白基础画布, 8(基础大小) *px_size(头颅大小) * px_mutil(全头大小)
                            (int(8 * px_size * px_mutil * render_scale), int(8 * px_size * px_mutil * render_scale)),
                            (0, 0, 0, 0))
    scaled_head = head.resize(
        (int(8 * px_size * render_scale), int(8 * px_size * render_scale)),
        Image.Resampling.BOX)
    base_canvas.paste(scaled_head, (int((8 * px_size * px_mutil - 8 * px_size) * render_scale / 2),
                                    int((8 * px_size * px_mutil - 8 * px_size) * render_scale / 2)))
    scaled_wear = head_wear.resize(
        (int(8 * px_size * px_mutil * render_scale), int(8 * px_size * px_mutil * render_scale)),
        Image.Resampling.BOX)
    base_canvas.paste(scaled_wear, (0, 0), mask=scaled_wear)
    return base_canvas
