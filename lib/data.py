from ctypes import windll
from dataclasses import dataclass
from hashlib import md5
from os import listdir, remove, mkdir
from os.path import join
from random import randbytes

from lib.config import *
from lib.log import logger

MAX_SIZE = (windll.user32.GetSystemMetrics(0), windll.user32.GetSystemMetrics(1))


@dataclass
class Player:
    """一只玩家"""
    name: str
    uuid: str = "00000000-0000-0000-0000-000000000000"

    def to_dict(self):
        return {"name": self.name, "uuid": self.uuid}

    @staticmethod
    def from_dict(dic: dict) -> "Player":
        return Player(**dic)

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Player):
            return self.name == other.name
        return False


def slice_dict(d: dict, start: int, end: int) -> dict:
    """
    按照key值对字典进行排序，并返回指定开始和结束位置的片段。

    参数:
    - d: 要排序和切片的字典。
    - start: 切片的起始位置。
    - end: 切片的结束位置。

    返回:
    - 排序并切片后的字典。
    """
    # 按照key值对字典进行排序，并提取排序后的key列表
    sorted_keys = sorted(d.keys())

    # 使用切片操作获取指定范围内的key
    sliced_keys = sorted_keys[start:end]

    # 构建并返回新的字典
    return {k: d[k] for k in sliced_keys}


class ServerPoint:
    """一个服务器数据点"""

    def __init__(self, time: float, online: int, players: list[Player], ping: float, **_):
        self.time = time  # (sec)
        self.online = online
        self.players = players
        self.ping = ping  # (ms)
        self.id_ = randbytes(8).hex()

    def to_dict(self):
        return {
            "time": self.time,
            "online": self.online,
            "players": [player.to_dict() for player in self.players],
            "ping": self.ping,
        }

    def copy(self, time: float):
        return ServerPoint(time, self.online, self.players, self.ping)

    @staticmethod
    def from_dict(dic: dict) -> "ServerPoint":
        players = [Player.from_dict(p) for p in dic.pop("players")]
        return ServerPoint(**dic, players=players)


class DataManager:
    """
    用于加载、修改、保存数据
    """

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.non_saved_counter = 0
        self.points_map: dict[str, ServerPoint] = {}
        self.data_files: list[str] = []
        if not exists(self.data_dir):
            logger.info(f"创建目录 [{self.data_dir}]...")
            mkdir(self.data_dir)

    @property
    def points(self):
        return self.points_map.values()

    def add_point(self, point: ServerPoint):
        """
        添加一个数据点
        :param point: 数据点
        """
        self.points_map[point.id_] = point
        self.non_saved_counter += 1
        if self.non_saved_counter >= config.saved_per_points:
            self.save_data()
            self.non_saved_counter = 0

    def remove_point(self, point: ServerPoint):
        """
        删除一个数据点
        :param point: 数据点
        """
        self.points_map.pop(point.id_)

    def load_data(self):
        """从预设好的文件夹中加载数据点"""
        logger.info(f"从 [{self.data_dir}] 加载数据...")
        for file in listdir(self.data_dir):
            self.data_files.append(file)  # 把启动时加载的文件名记录下来
            full_path = join(self.data_dir, file)
            logger.info(f"加载文件 [{file}]")
            with open(full_path, "r") as f:
                file_dic: list[dict] = json.load(f)
            for point_dict in file_dic:
                point = ServerPoint.from_dict(point_dict)
                self.points_map[point.id_] = point

        sorted_points = sorted(self.points_map.values(), key=lambda pt: pt.time)
        self.points_map = {point.id_: point for point in sorted_points}
        logger.info(f"加载完成，共 {len(self.points_map)} 个数据点")

    def save_data(self):
        """
        保存数据到预设好的文件夹中
        tip: 会比对文件哈希值并删除失效的数据文件
        """
        if not config.enable_data_save:
            logger.info("数据保存已禁用，跳过保存")
            return
        logger.info(f"保存数据到 [{self.data_dir}]...")
        self.data_files.clear()
        ready_points: list[dict] = []
        points_counter = 0

        for point in self.points_map.values():
            ready_points.append(point.to_dict())
            points_counter += 1
            if points_counter >= config.points_per_file:
                self.dump_points(ready_points)
                ready_points = []
                points_counter = 0
        if ready_points:
            self.dump_points(ready_points)

        failure_files = listdir(self.data_dir)
        for file in self.data_files:
            if file in failure_files:
                failure_files.remove(file)
        for file in failure_files:
            logger.info(f"移除失效文件 [{file}]...")
            remove(join(self.data_dir, file))

    def dump_points(self, points: list[dict]):
        """存储一个数据点进文件, 把所有数据点的时间作哈希"""
        points_hash = md5(usedforsecurity=False)
        for ready_point in points:
            points_hash.update(str(ready_point["time"]).encode())
        hash_hex = points_hash.hexdigest()
        save_path = join(self.data_dir, hash_hex + ".json")

        self.data_files.append(hash_hex + ".json")
        if not exists(save_path):
            with open(save_path, "w") as f:
                # noinspection PyTypeChecker
                json.dump(points, f)
                logger.info(f"保存文件 [{hash_hex + '.json'}] ...")


class DataFilter:
    def __init__(self, from_time: float = None, to_time: float = None):
        self.from_time = from_time
        self.to_time = to_time

    def filter_points(self, points: dict[float, ServerPoint]):
        if self.from_time is None and self.to_time is None:
            return list(points.values())
        return [point for point in points.values() if self.from_time <= point.time <= self.to_time]

    def check(self, point: ServerPoint):
        if self.from_time is None and self.to_time is None:
            return True
        return self.from_time <= point.time <= self.to_time
