"""
这个文件做一些操作数据的东西
定义数据点类
定义数据存储类
定义数据过滤类
"""
from copy import copy
from ctypes import windll
from dataclasses import dataclass
from hashlib import md5
from os import listdir, remove, mkdir
from os.path import join, basename, isfile
from random import randbytes
from threading import Lock, Thread, current_thread

from lib.config import *
from lib.log import logger
from lib.perf import Counter

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
    :param d: 要排序+切片的字典
    :param start: 切片的起始位置
    :param end: 切片的结束位置

    返回:
    - 排序并切片后的字典。
    """
    # 按照key值对字典进行排序，并提取排序后的key列表
    sorted_keys = sorted(d.keys())

    # 使用切片操作获取指定范围内的key
    sliced_keys = sorted_keys[start:end]

    # 构建并返回新的字典
    return {k: d[k] for k in sliced_keys}


def get_players_hash(players: list[dict[str, str]]) -> str:
    """
    计算玩家列表的哈希值
    :param players: 玩家列表
    :return: 哈希值
    """
    players_hash = md5()
    for player in players:
        players_hash.update(player["name"].encode())
        players_hash.update(player["uuid"].encode())
    return players_hash.hexdigest()


class ServerPoint:
    """数据点类"""

    def __init__(self, time: float, online: int, players: list[Player], ping: float = 0, **_):
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
            **({"ping": self.ping} if self.ping != 0 else {}),
        }

    def copy(self, time: float = None):
        time = time if time is not None else self.time
        return ServerPoint(time, self.online, self.players, self.ping)

    @staticmethod
    def from_dict(dic: dict) -> "ServerPoint":
        players = [Player.from_dict(p) for p in dic.pop("players")]
        return ServerPoint(**dic, players=players)


def dumps_player_list_mapping(points: list[dict]):
    player_list_map: dict[str, list[dict[str, str]]] = {}
    for i, pt in enumerate(points):
        players: list[dict[str, str]] = copy(pt["players"])
        player_list_id: str = get_players_hash(players)
        if player_list_id not in player_list_map:
            player_list_map[player_list_id] = players
        pt["players"] = player_list_id
    return {
        "fmt": DataSaveFmt.PLAYER_LIST_MAPPING.value,
        "points": points,
        "players_mapping": player_list_map,
    }


def dumps_player_mapping(points: list[dict]):
    player_list_map: dict[str, list[str]] = {}
    players_map: dict[str, dict[str, str]] = {}
    mapped_players = set()
    for i, pt in enumerate(points):
        raw_players: list[dict[str, str]] = copy(pt["players"])
        players = [p["name"] for p in raw_players]
        player_list_id: str = get_players_hash(raw_players)
        if player_list_id not in player_list_map:
            player_list_map[player_list_id] = players
        pt["players"] = player_list_id
        for player in raw_players:
            if player["name"] not in mapped_players:
                players_map[player["name"]] = player
                mapped_players.add(player["name"])
    return {
        "fmt": DataSaveFmt.PLAYER_MAPPING.value,
        "points": points,
        "player_list_mapping": player_list_map,
        "players_mapping": players_map,
    }


class DataManager:
    """
    用于管理数据点加载、修改、保存的类
    """

    def __init__(self, data_dir: str):
        self.data_ctl_lock = Lock()
        self.data_dir = data_dir
        self.non_saved_counter = 0
        self.points_map: dict[str, ServerPoint] = {}
        self.data_files: list[str] = []
        if not exists(self.data_dir):
            logger.info(f"创建目录 [{self.data_dir}]...")
            mkdir(self.data_dir)
        self.last_fmt: DataSaveFmt = config.data_save_fmt

    @property
    def points(self):
        return self.points_map.values()

    def add_point(self, point: ServerPoint):
        """
        添加一个数据点
        :param point: 数据点
        """
        with self.data_ctl_lock:
            self.points_map[point.id_] = point
            self.non_saved_counter += 1
        if self.non_saved_counter >= config.saved_per_points:
            self.save_data()
            self.non_saved_counter = 0

    def get_point(self, point_id: str) -> ServerPoint:
        """
        获取一个数据点
        :param point_id: 数据点的id
        :return: 数据点
        """
        return self.points_map[point_id]

    def remove_point(self, point: ServerPoint):
        """
        删除一个数据点
        :param point: 数据点
        """
        with self.data_ctl_lock:
            self.points_map.pop(point.id_)

    def load_data(self):
        """从文件夹中查找并加载数据点"""
        logger.info(f"从 [{self.data_dir}] 加载数据...")
        load_threads = []
        lock = Lock()
        with self.data_ctl_lock:
            timer = Counter()
            timer.start()
            for file in listdir(self.data_dir):
                self.data_files.append(file)  # 把启动时加载的文件名记录下来
                full_path = join(self.data_dir, file)
                thread = Thread(name=f"Loader-{str(len(load_threads)).zfill(2)}", target=self.load_a_file,
                                args=(full_path, lock))
                thread.start()
                load_threads.append(thread)
                if len(load_threads) >= config.data_load_threads:
                    removed_threads = []
                    for thread in load_threads:
                        if not thread.is_alive():
                            removed_threads.append(thread)
                    for thread in removed_threads:
                        load_threads.remove(thread)
                    del removed_threads
                    if len(load_threads) >= config.data_load_threads:
                        load_threads[0].join()
                        load_threads.pop(0)
            for thread in load_threads:
                thread.join()

            sorted_points = sorted(self.points_map.values(), key=lambda pt: pt.time)
            self.points_map = {point.id_: point for point in sorted_points}
        logger.info(f"加载完成, 共 {len(self.points_map)} 个数据点, 耗时 {timer.endT()}")

    def load_a_file(self, file_path: str, lock: Lock):
        """
        从给定的文件路径加载数据点
        旧格式: list[dict[]], 新格式: dict[str, Any]
        :param file_path: 文件路径
        :param lock: 字典操作的锁
        """
        thr_name = current_thread().name
        with open(file_path, "r") as f:
            data_obj: list[dict] = json.load(f)
        logger.info(f"[{thr_name}] 已加载文件 [{basename(file_path)}]")
        with lock:
            if isinstance(data_obj, list):
                for point_dict in data_obj:
                    point = ServerPoint.from_dict(point_dict)
                    self.points_map[point.id_] = point
            elif isinstance(data_obj, dict) and data_obj["fmt"] == DataSaveFmt.PLAYER_LIST_MAPPING.value:
                player_list_map_t1: dict[str, list[dict[str, str]]] = data_obj["players_mapping"]
                for point_dict in data_obj["points"]:
                    players_list_id: str = point_dict["players"]
                    if players_list_id in player_list_map_t1:
                        point_dict["players"] = player_list_map_t1[players_list_id]
                    else:
                        point_dict["players"] = []
                        logger.warning(
                            f"[{thr_name}] 玩家映射文件 [{basename(file_path)}] 中找不到玩家映射 {players_list_id}")
                    point = ServerPoint.from_dict(point_dict)
                    self.points_map[point.id_] = point
            elif isinstance(data_obj, dict) and data_obj["fmt"] == DataSaveFmt.PLAYER_MAPPING.value:
                player_list_map_t2: dict[str, list[str]] = data_obj["player_list_mapping"]
                players_map: dict[str, dict[str, str]] = data_obj["players_mapping"]
                for point_dict in data_obj["points"]:
                    player_list_id = point_dict["players"]
                    if player_list_id in player_list_map_t2:
                        players = player_list_map_t2[player_list_id]
                    else:
                        players = []
                        logger.warning(
                            f"[{thr_name}] 玩家映射文件 [{basename(file_path)}] 中找不到玩家映射 {player_list_id}")
                    raw_players = [players_map[name] for name in players]
                    point_dict["players"] = raw_players

    def save_data(self) -> None | str:
        """
        保存数据到预设好的文件夹中
        tip: 会比对文件哈希值并删除失效的数据文件
        """
        if not config.enable_data_save:
            logger.info("数据保存已禁用，跳过保存")
            return None
        data_save_fmt: DataSaveFmt = copy(config.data_save_fmt)
        logger.info(f"保存数据到 [{self.data_dir}]... 格式: {data_save_fmt.name}")
        self.data_files.clear()
        ready_points: list[dict] = []
        points_counter = 0
        rewrite_data = False
        if self.last_fmt != data_save_fmt:
            self.last_fmt = data_save_fmt
            rewrite_data = True

        with self.data_ctl_lock:
            points_length = len(self.points_map)
            for index, point in enumerate(self.points_map.values()):
                ready_points.append(point.to_dict())
                points_counter += 1
                if points_counter >= config.points_per_file or index == points_length - 1:
                    try:
                        self.dump_points(ready_points, data_save_fmt, rewrite_data)
                    except OSError as e:
                        logger.error(f"保存数据时发生错误, 终止保存 -> {e}")
                        return f"保存数据时发生错误, 终止保存 -> {e}"
                    ready_points = []
                    points_counter = 0

        failure_files = listdir(self.data_dir)
        for file in self.data_files:
            if file in failure_files:
                failure_files.remove(file)
        for file in failure_files:
            full_path = join(self.data_dir, file)
            try:
                if exists(full_path) and isfile(full_path):
                    remove(full_path)
                    logger.info(f"移除失效文件 [{file}]...")
                else:
                    logger.warning(f"文件 [{file}] 不存在, 跳过删除")
            except OSError as e:
                logger.error(f"移除失效文件时发生系统错误, 终止保存 -> {e}")
                return f"移除失效文件时发生错误, 终止保存 -> {e}"

    def dump_points(self, points: list[dict], fmt: DataSaveFmt, rewrite_data: bool = False):
        """
        存储给定的数据点字典到文件, 把所有数据点的时间作md5哈希作为文件名
        :param points: 数据点字典列表
        :param fmt: 数据存储格式
        :param rewrite_data: 是否覆盖已存在的文件
        """
        points_hash = md5(usedforsecurity=False)
        for ready_point in points:
            points_hash.update(str(ready_point["time"]).encode())
        hash_hex = points_hash.hexdigest()
        save_path = join(self.data_dir, hash_hex + ".json")

        if not exists(save_path) or rewrite_data:
            if fmt == DataSaveFmt.NORMAL:
                final_content = points
            elif fmt == DataSaveFmt.PLAYER_LIST_MAPPING:
                final_content = dumps_player_list_mapping(points)
            elif fmt == DataSaveFmt.PLAYER_MAPPING:
                final_content = dumps_player_mapping(points)
            else:
                logger.error(f"未知的存储格式 -> {fmt}")
                return
            with open(save_path, "w") as f:
                # noinspection PyTypeChecker
                json.dump(final_content, f)
            logger.info(f"保存文件 [{hash_hex + '.json'}]")
        self.data_files.append(hash_hex + ".json")

    def get_all_online_ranges(self) -> dict[str, list[tuple[float, float]]]:
        """
        获取所有玩家的在线时间段范围
        :return: 一个字典，键为玩家名称，值为该玩家的所有在线时间段列表
        """
        player_active_times: dict[str, list[tuple[float, float | None]]] = {}  # 记录每个玩家的在线时间段
        range_start_players: dict[str, float] = {}
        last_players = set()  # 上一个数据点中的玩家集合
        last_point = None
        points_len = len(self.points_map)
        with self.data_ctl_lock:
            for i, point in enumerate(self.points):
                now_players = set(p.name for p in point.players)  # 当前数据点中的玩家集合

                # 处理新上线的玩家
                for player in now_players - last_players:
                    range_start_players[player] = point.time

                # 处理下线的玩家
                for player in last_players - now_players:
                    if player not in player_active_times:
                        player_active_times[player] = []
                    player_active_times[player].append((range_start_players.pop(player), point.time))  # 记录上线时间

                last_players = now_players
                if i == points_len - 1:
                    last_point = point

        # 处理仍然在线的玩家
        for player, start in range_start_players.items():
            if player not in player_active_times:
                player_active_times[player] = []
            player_active_times[player].append((start, last_point.time))

        # 转换为元组形式
        return player_active_times

    def get_player_online_ranges(self, player_name: str) -> list[tuple[float, float]]:
        """
        获取某个玩家所有在线时间段的列表
        :param player_name: 玩家名称
        """
        last_players: set[str] = set()
        active_start: float = 0
        result: list[tuple[float, float]] = []
        points_count = len(self.points_map)
        with self.data_ctl_lock:
            for i, point in enumerate(self.points):
                if i == 0:
                    active_start = point.time
                now_players = set(p.name for p in point.players)
                for player in now_players - last_players:
                    if player == player_name:
                        active_start = point.time
                for player in last_players - now_players:
                    if player == player_name:
                        result.append((active_start, point.time))
                        active_start = 0
                last_players = now_players
                if i >= points_count - 1 and active_start != 0:
                    result.append((active_start, point.time))
        return result


class DataFilter:
    """一个简单的数据过滤器, 通过给定的开始时间和结束时间过滤数据"""

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
