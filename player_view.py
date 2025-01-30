from datetime import datetime, date, time
from threading import Thread
from time import perf_counter, strftime, localtime

import wx

from config import config
from data import DataManager, Player
from log import logger


class PlayerOnlineInfo:
    """玩家在线信息"""

    def __init__(self, name: str, last_offline_time: int):
        self.name: str = name
        self.last_offline_time: float = last_offline_time
        self.total_online_time: float = 0
        self.today_online_time: float = 0
        self.avg_online_per_day: float = 0
        self.avg_online_per_session: float = 0
        self.max_online_per_session: float = 0
        self.online_times: list[tuple[float, float]] = []


def string_fmt_time(seconds: float) -> str:
    """格式化时间戳至字符串"""
    time_str = ""
    time_tuple = tuple_fmt_time(seconds)
    if time_tuple[0] > 0:
        time_str += f"{time_tuple[0]}d "
    if time_tuple[1] > 0:
        time_str += f"{time_tuple[1]}h "
    if time_tuple[2] > 0:
        time_str += f"{time_tuple[2]}m "
    if time_tuple[3] > 0:
        time_str += f"{time_tuple[3]}s"
    return time_str


def tuple_fmt_time(seconds: float) -> tuple[int, int, int, int]:
    """转化时间戳至时间元组"""
    return int(seconds // 3600 // 24), int(seconds // 3600 % 24), int(seconds % 3600 // 60), int(seconds % 60)


def sort_players_info(players_info: dict[str, PlayerOnlineInfo], column: int, ascending: bool) -> dict[
    str, PlayerOnlineInfo]:
    """根据指定列对玩家信息进行排序"""
    players_list = list(players_info.values())
    if column == 0:
        players_list.sort(key=lambda x: x.name, reverse=not ascending)
    elif column == 1:
        players_list.sort(key=lambda x: x.total_online_time, reverse=not ascending)
    elif column == 2:
        players_list.sort(key=lambda x: x.today_online_time, reverse=not ascending)
    elif column == 3:
        players_list.sort(key=lambda x: x.avg_online_per_day, reverse=not ascending)
    elif column == 4:
        players_list.sort(key=lambda x: len(x.online_times), reverse=not ascending)
    elif column == 5:
        players_list.sort(key=lambda x: x.avg_online_per_session, reverse=not ascending)
    elif column == 6:
        players_list.sort(key=lambda x: x.max_online_per_session, reverse=not ascending)
    elif column == 7:
        players_list.sort(key=lambda x: x.last_offline_time, reverse=not ascending)

    return {player.name: player for player in players_list}


class PlayerViewPanel(wx.Panel):
    """玩家在线信息面板"""

    def __init__(self, parent: wx.Window, data_manager: DataManager):
        super().__init__(parent)
        self.data_manager = data_manager  # 初始化数据管理器用于数据操作
        self.sort_column = 1  # 设置默认排序列为第1列
        self.sort_ascending = False  # 降序排列
        self.activate_datas = {}  # 初始化激活数据字典

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.start_analyze_btn = wx.Button(self, label="开始分析")
        self.analyze_gauge = wx.Gauge(self, range=100, style=wx.GA_SMOOTH | wx.GA_TEXT)
        self.player_info_lc = wx.ListCtrl(self, style=wx.LC_REPORT)
        column_map = [
            ("玩家名", 250),
            ("总在线时长", 150),
            ("今天在线时长", 150),
            ("天平均在线", 150),
            ("在线次数", 100),
            ("平均每次在线", 150),
            ("最长单次在线", 150),
            ("最后在线时刻", 200)
        ]
        for i, (name, width) in enumerate(column_map):
            self.player_info_lc.InsertColumn(i, name, width=width, format=wx.LIST_FORMAT_CENTER)
        self.start_analyze_btn.SetMaxSize((-1, 50))
        self.start_analyze_btn.SetMinSize((-1, 50))
        self.analyze_gauge.SetMaxSize((-1, 30))
        sizer.Add(self.start_analyze_btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=5)
        sizer.AddSpacer(5)
        sizer.Add(self.analyze_gauge, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5)
        sizer.AddSpacer(5)
        sizer.Add(self.player_info_lc, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        self.SetSizer(sizer)

        self.analyze_thread = Thread(target=self.analyze_players)
        self.start_analyze_btn.Bind(wx.EVT_BUTTON, self.start_analyze)
        self.player_info_lc.Bind(wx.EVT_LIST_COL_CLICK, self.on_column_click)

    def start_analyze(self, _):
        """启动分析任务"""
        self.analyze_gauge.SetValue(0)
        self.analyze_thread = Thread(target=self.analyze_players)
        self.analyze_thread.start()

    def analyze_players(self):
        """分析玩家在线信息"""
        players_info = self.get_player_infos()  # 获取玩家在线信息
        sorted_players_info = sort_players_info(players_info, self.sort_column, self.sort_ascending)
        self.activate_datas = sorted_players_info
        self.populate_list(sorted_players_info)

    def populate_list(self, players_info: dict[str, PlayerOnlineInfo]):
        """填充玩家信息到列表控件"""
        self.player_info_lc.DeleteAllItems()
        for player_info in players_info.values():
            self.add_player(player_info)

    def add_player(self, player: PlayerOnlineInfo):
        """添加一组信息进入列表"""
        line = self.player_info_lc.GetItemCount()
        self.player_info_lc.InsertItem(line, player.name)
        self.player_info_lc.SetItem(line, 1, string_fmt_time(player.total_online_time))
        self.player_info_lc.SetItem(line, 2, string_fmt_time(player.today_online_time))
        self.player_info_lc.SetItem(line, 3, string_fmt_time(player.avg_online_per_day))
        self.player_info_lc.SetItem(line, 4, str(len(player.online_times)))
        self.player_info_lc.SetItem(line, 5, string_fmt_time(player.avg_online_per_session))
        self.player_info_lc.SetItem(line, 6, string_fmt_time(player.max_online_per_session))
        self.player_info_lc.SetItem(line, 7, strftime("%y-%m-%d %H:%M:%S", localtime(player.last_offline_time)))

    def get_player_infos(self) -> dict[str, PlayerOnlineInfo]:
        """获取玩家在线时间信息"""
        last_players: set[Player] = set()
        player_infos: dict[str, PlayerOnlineInfo] = {}
        length = len(self.data_manager.points)
        last_progress = perf_counter()
        logger.info("开始分析玩家数据")
        for i, point in enumerate(self.data_manager.points):
            players_set = set(point.players)  # 获取当前数据点的玩家集合
            # 计算新增和下线玩家
            added_players = players_set - last_players  # 获取新增玩家的集合
            for player in added_players:
                if player.name not in player_infos:
                    player_infos[player.name] = PlayerOnlineInfo(player.name, point.time)  # 新增当前不存在在线数据的玩家
                else:
                    player_infos[player.name].last_offline_time = point.time  # 修改已存在玩家的最后在线时间

            if i == length - 1:  # 获取下线玩家的集合, 最后的数据点处理所有玩家
                lose_players = players_set
            else:
                lose_players = last_players - players_set
            for player in lose_players:
                info = player_infos[player.name]
                info.online_times.append((info.last_offline_time, point.time))  # 添加玩家在线时间段
                info.total_online_time += point.time - info.last_offline_time  # 累加玩家在线时间
                info.last_offline_time = point.time  # 修改玩家最后在线时间

            # 善后工作awa
            last_players = players_set
            if perf_counter() - last_progress > 0.5:  # OMG这个脚本怎么跑这么快
                wx.CallAfter(self.analyze_gauge.SetValue, (i / length) * 100)
                last_progress = perf_counter()

        wx.CallAfter(self.analyze_gauge.SetValue, 100)
        logger.info("分析完成")
        for info in player_infos.values():
            # 合并或删除在线时间段
            merged_online_times = []
            i =     0
            while i < len(info.online_times):
                start, end = info.online_times[i]
                if end - start < config.min_online_time:
                    # 如果在线时间小于min_online_time，检查是否可以与下一个时间段合并
                    if i + 1 < len(info.online_times) and info.online_times[i + 1][0] - end < config.min_online_time:
                        # 合并时间段
                        end = info.online_times[i + 1][1]
                        i += 1  # 跳过下一个时间段
                else:
                    # 否则，添加到合并列表
                    merged_online_times.append((start, end))
                i += 1

            info.online_times = merged_online_times
            info.total_online_time = sum(end - start for start, end in info.online_times)  # 重新计算总在线时间

            if not info.online_times:
                continue

            # 计算玩家平均每天在线时间
            days = set() # 计算玩家在线天数
            for start, end in info.online_times:
                dt_obj = datetime.fromtimestamp(start)
                days.add(str(dt_obj.date()))
            info.avg_online_per_day = info.total_online_time / len(days) # 总时间 / 玩家在线天数

            # 计算玩家平均每次在线时间
            times = len(info.online_times)  # 计算玩家在线次数
            info.avg_online_per_session = info.total_online_time / times  # 总时间 / 玩家在线次数

            # 计算玩家最大在线时间
            info.max_online_per_session = 0
            for start, stop in info.online_times:
                during = stop - start
                if during > info.max_online_per_session:  # 超过则代替
                    info.max_online_per_session = during

            # 计算玩家今天在线时间
            day_start = datetime.combine(date.today(), time()).timestamp()
            day_end = datetime.combine(date.today(), time(23, 59, 59)).timestamp()
            match_times = [(start, stop) for start, stop in info.online_times if start >= day_start and stop <= day_end]
            info.today_online_time = sum(stop - start for start, stop in match_times)

            logger.debug(
                f"玩家: {info.name}, "
                f"在线时间: {info.total_online_time}, "
                f"平均在线时间: {info.avg_online_per_session}, "
                f"平均每天在线时间: {info.avg_online_per_day}, "
                f"最大在线时间: {info.max_online_per_session}, "
                f"今日在线时间: {info.today_online_time}"
            )

        return player_infos

    def on_column_click(self, event):
        """列头点击事件处理函数"""
        column = event.GetColumn()
        if self.sort_column == column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = column
            self.sort_ascending = True

        sorted_players_info = sort_players_info(self.activate_datas, column, self.sort_ascending)
        self.populate_list(sorted_players_info)
