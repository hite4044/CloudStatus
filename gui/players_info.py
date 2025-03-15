"""
玩家面板
提供 玩家在线数据 查看的GUI定义文件
"""
from datetime import datetime, timedelta
from threading import Thread
from time import perf_counter, strftime, localtime

import wx

from gui.events import PlayerOnlineInfoEvent, EVT_PLAYER_ONLINE_INFO, AddPlayersOverviewEvent
from gui.widget import TimeSelector, ft, string_fmt_time
from gui.online_widget import PlayerOnlineWin
from lib.common_data import common_data
from lib.config import config
from lib.data import Player
from lib.log import logger

players_sort_map = {
    1: "x.name",
    2: "x.total_online_time",
    3: "x.today_online_time",
    4: "x.avg_online_per_day",
    5: "len(x.online_times)",
    6: "x.avg_online_per_session",
    7: "x.max_online_per_session",
    8: "x.last_offline_time",
    9: "x.join_server_time"
}


class PlayerOnlineInfo:
    """一个玩家的在线信息"""

    def __init__(self, name: str, last_offline_time: float):
        self.name: str = name
        self.last_offline_time: float = last_offline_time
        self.join_server_time: float = last_offline_time
        self.total_online_time: float = 0
        self.today_online_time: float = 0
        self.avg_online_per_day: float = 0
        self.avg_online_per_session: float = 0
        self.max_online_per_session: float = 0
        self.online_times: list[tuple[float, float]] = []


def sort_players_info(players_info: dict[str, PlayerOnlineInfo], column: int, ascending: bool) -> dict[
    str, PlayerOnlineInfo]:
    """根据指定列对玩家信息进行排序"""
    players_list = list(players_info.values())
    players_list.sort(key=lambda x: eval(players_sort_map[column]), reverse=not ascending)
    return {player.name: player for player in players_list}


class OnlineTimeFilter:
    def __init__(self, from_time: float = None, to_time: float = None):
        self.from_time = from_time
        self.to_time = to_time

    def filter(self, range_: tuple[float, float]) -> tuple[float, float] | None:
        """过滤并截断时间范围"""
        if self.from_time is None or self.to_time is None:
            return range_
        if self.from_time < range_[0] < self.to_time and self.from_time < range_[1] < self.to_time:
            return range_
        elif range_[0] < self.from_time < range_[1] < self.to_time:
            return self.from_time, range_[1]
        elif self.from_time < range_[0] < self.to_time < range_[1]:
            return range_[0], self.to_time
        else:
            return None


class OnlineInfoColor:
    BACKGROUND = (230, 230, 230)
    BAR = (6, 176, 37)
    BORDER = (188, 188, 188)


class OnlineInfoLine(wx.Control):
    def __init__(self, parent: wx.Window, online_times: list[tuple[float, float]], range_: tuple[float, float]):
        super().__init__(parent, wx.ID_ANY, wx.DefaultPosition, (-1, 70), wx.NO_BORDER, wx.DefaultValidator,
                         "OnlineInfoLine")
        self.SetMinSize((1140, 70))
        self.online_times = online_times
        self.range_ = range_

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_MOTION, self.on_mouse_move)  # 绑定鼠标移动事件

        self.tooltip = wx.ToolTip("")
        self.SetToolTip(self.tooltip)  # 设置工具提示

    def on_paint(self, _):
        dc = wx.PaintDC(self)

        min_time, max_time = self.range_

        width, height = self.GetClientSize()
        width -= 2
        height -= 2

        dc.SetBrush(wx.Brush(OnlineInfoColor.BACKGROUND))
        dc.DrawRectangle(-1, -1, width + 4, height + 4)
        dc.Clear()
        dc.SetPen(wx.Pen(OnlineInfoColor.BAR))
        dc.SetBrush(wx.Brush(OnlineInfoColor.BAR))  # 因为不知道怎么不画出边框，所以用同样的颜色掩盖一下

        for online_time in self.online_times:
            start_percent = (online_time[0] - min_time) / (max_time - min_time)
            end_percent = (online_time[1] - min_time) / (max_time - min_time)
            dc.DrawRectangle(int(start_percent * width), 1, int((end_percent - start_percent) * width), height - 2)

        dc.SetPen(wx.Pen(OnlineInfoColor.BORDER))
        dc.DrawLines([(0, 0), (width + 1, 0), (width + 1, height + 1), (0, height + 1), (0, 0)])

    def on_size(self, event):
        self.Refresh()
        event.Skip()

    def on_mouse_move(self, event):
        x, y = event.GetPosition()
        min_time, max_time = self.range_
        width, height = self.GetClientSize()
        width -= 2
        height -= 2

        # 计算鼠标指针对应的时间
        if 0 <= x <= width and 0 <= y <= height:
            time_percent = x / width
            time_at_mouse = min_time + time_percent * (max_time - min_time)
            time_str = string_fmt_time(time_at_mouse - min_time)
            self.tooltip.SetTip(f"Time: {time_str}")
        else:
            self.tooltip.SetTip("")

        event.Skip()


# noinspection PyPep8Naming
class PlayerOnlinePanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        # 创建时间选择控件并狠狠地给它注入两个按钮
        self.time_selector = TimeSelector(self)
        self.load_btn = wx.Button(self.time_selector, label="加载")
        self.reset_btn = wx.Button(self.time_selector, label="重置")
        self.time_selector.label_hour.SetLabel("天起始:")
        self.time_selector.hour_ctrl.SetValue(4)
        widget_sizer: wx.BoxSizer = self.time_selector.GetSizer()
        widget_sizer.InsertStretchSpacer(0, 1)
        widget_sizer.AddStretchSpacer(1)
        widget_sizer.Add(self.reset_btn)
        widget_sizer.Add(self.load_btn)

        vbox = wx.BoxSizer(wx.VERTICAL)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.scroll_panel = wx.ScrolledWindow(self)
        self.scroll_panel.SetScrollbars(1, 1, 0, 450)
        self.scroll_panel.SetScrollRate(20, 20)  # 滚动速度
        self.data_panel = wx.Panel(self.scroll_panel)
        vbox.Add(self.data_panel, wx.EXPAND)

        self.scroll_panel.SetSizer(vbox)
        self.sizer.Add(self.time_selector, flag=wx.EXPAND, proportion=0)
        self.sizer.Add(self.scroll_panel, flag=wx.EXPAND, proportion=1)
        self.SetSizer(self.sizer)

        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_filter_update)
        self.load_btn.Bind(wx.EVT_BUTTON, self.on_filter_update)

        self.raw_data: dict[str, list[tuple[float, float]]] = {}
        self.active_datas: dict[str, list[tuple[float, float]]] = {}
        self.active_filter: OnlineTimeFilter = OnlineTimeFilter()

        self.data_sizer = wx.FlexGridSizer(0, 2, 5, 5)
        self.data_panel.SetFont(ft(36))
        self.data_sizer.Add(wx.StaticText(self.data_panel, label="这里找不到数据 /_ \\ \n你可以试试先在左边分析下"), wx.EXPAND)
        self.data_panel.SetFont(ft(12))
        self.data_panel.SetSizer(self.data_sizer)

    def on_filter_update(self, event: wx.Event):
        if event.GetEventObject() == self.reset_btn:
            self.active_filter = OnlineTimeFilter()
        else:
            if self.time_selector.hour_enable:
                r = self.time_selector.hour_enable = False
            else:
                r = True
            start, end = self.time_selector.get_time_range()
            start += timedelta(hours=self.time_selector.hour_ctrl.GetValue())
            end += timedelta(hours=self.time_selector.hour_ctrl.GetValue())
            self.active_filter = OnlineTimeFilter(start.timestamp(), end.timestamp())
            if not r:
                self.time_selector.hour_enable = True
        self.filter_data()
        self.redraw()

    def update_data(self, datas: dict[str, list[tuple[float, float]]]):
        self.raw_data = datas
        self.filter_data()
        self.redraw()

    def filter_data(self):
        self.active_datas.clear()
        for player_name, online_times in self.raw_data.items():
            for online_time in online_times:
                result = self.active_filter.filter(online_time)
                if not result:
                    continue
                if player_name not in self.active_datas:
                    self.active_datas[player_name] = []
                self.active_datas[player_name].append(result)

    def redraw(self):
        self.Freeze()
        for child in self.data_sizer.GetChildren():
            child.GetWindow().Destroy()
        self.data_sizer.SetRows(len(self.active_datas))
        if self.active_filter.from_time:
            range_ = (self.active_filter.from_time, self.active_filter.to_time)
        else:
            range_ = {0: 1145141919810, 1: 1145141919811}
            for online_time in self.active_datas.values():
                for time_ in online_time:
                    if time_[0] < range_[0]:
                        range_[0] = time_[0]
                    if time_[1] > range_[1]:
                        range_[1] = time_[1]
            range_ = (range_[0], range_[1])

        for player_name, online_times in self.active_datas.items():
            self.data_sizer.Add(wx.StaticText(self.data_panel, label=player_name), proportion=0)
            self.data_sizer.Add(OnlineInfoLine(self.data_panel, online_times, range_), flag=wx.EXPAND, proportion=1)
        if not self.active_datas:
            self.data_sizer.Add(wx.StaticText(self.data_panel, label="这里找不到数据 /_ \\"), wx.EXPAND)
        self.data_panel.Layout()
        self.scroll_panel.Layout()
        self.Layout()
        self.Thaw()


class PlayerPanel(wx.Notebook):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.player_info_panel = PlayerInfoPanel(self)
        self.player_online_panel = PlayerOnlinePanel(self)
        self.AddPage(self.player_info_panel, "在线信息")
        self.AddPage(self.player_online_panel, "在线时间段")
        self.player_info_panel.Bind(EVT_PLAYER_ONLINE_INFO,
                                    lambda e: self.player_online_panel.update_data(e.players_info))


class PlayerInfoPanel(wx.Panel):
    """玩家在线信息面板"""

    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = timedelta(days=1) + day_start
        self.active_filter = OnlineTimeFilter(day_start.timestamp(), day_end.timestamp())
        self.data_manager = common_data.data_manager  # 获取数据管理器用于数据操作
        self.sort_column = 1  # 设置默认排序列为第1列
        self.sort_ascending = False  # 降序排列
        self.activate_datas = {}  # 初始化激活数据字典

        sizer = wx.BoxSizer(wx.VERTICAL)
        # 创建时间选择控件并狠狠地给它注入两个按钮
        self.time_selector = TimeSelector(self)
        self.load_btn = wx.Button(self.time_selector, label="加载")
        self.reset_btn = wx.Button(self.time_selector, label="重置")
        self.time_selector.label_hour.SetLabel("天起始:")
        self.time_selector.hour_ctrl.SetValue(4)
        widget_sizer: wx.BoxSizer = self.time_selector.GetSizer()
        widget_sizer.InsertStretchSpacer(0, 1)
        widget_sizer.AddStretchSpacer(1)
        widget_sizer.Add(self.reset_btn)
        widget_sizer.Add(self.load_btn)
        self.start_analyze_btn = wx.Button(self, label="开始分析")
        self.analyze_gauge = wx.Gauge(self, range=100, style=wx.GA_SMOOTH | wx.GA_TEXT)

        self.player_info_lc = wx.ListCtrl(self, style=wx.LC_REPORT)
        column_map = [
            ("排名", 50),
            ("玩家名", 250),
            ("总在线时长", 150),
            ("今天在线时长", 150),
            ("天平均在线", 150),
            ("在线次数", 100),
            ("平均每次在线", 150),
            ("最长单次在线", 150),
            ("最近在线", 200),
            ("进服时间", 200)
        ]
        for i, (name, width) in enumerate(column_map):
            if i == 1:
                self.player_info_lc.InsertColumn(i + 1, name, width=width)
            else:
                self.player_info_lc.InsertColumn(i + 1, name, width=width, format=wx.LIST_FORMAT_CENTER)
        self.start_analyze_btn.SetMaxSize((-1, 50))
        self.start_analyze_btn.SetMinSize((-1, 50))
        self.analyze_gauge.SetMaxSize((-1, 30))
        sizer.Add(self.time_selector, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=5)
        sizer.AddSpacer(5)
        sizer.Add(self.start_analyze_btn, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5)
        sizer.AddSpacer(5)
        sizer.Add(self.analyze_gauge, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5)
        sizer.AddSpacer(5)
        sizer.Add(self.player_info_lc, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        self.SetSizer(sizer)

        self.analyze_thread = Thread(target=self.analyze_players)
        self.start_analyze_btn.Bind(wx.EVT_BUTTON, self.start_analyze)
        self.player_info_lc.Bind(wx.EVT_LIST_COL_CLICK, self.on_column_click)
        self.player_info_lc.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_menu)

        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_filter_update)
        self.load_btn.Bind(wx.EVT_BUTTON, self.on_filter_update)

    def on_menu(self, _):
        first = self.player_info_lc.GetFirstSelected()
        if first == -1:
            return
        selections = []
        while first != -1:
            selections.append(first)
            first = self.player_info_lc.GetNextSelected(first)
        first = selections[0]

        def get_data(line, column) -> str:
            return self.player_info_lc.GetItemText(line, column)

        def copy_detail():
            text = f"玩家: {get_data(first, 1)}\n"
            text += f"总在线时长: {get_data(first, 2)}\n"
            text += f"今天在线时长: {get_data(first, 3)}\n"
            text += f"天平均在线: {get_data(first, 4)}\n"
            text += f"在线次数: {get_data(first, 5)}\n"
            text += f"平均每次在线: {get_data(first, 6)}\n"
            text += f"最长单次在线: {get_data(first, 7)}\n"
            text += f"最近在线: {get_data(first, 8)}\n"
            text += f"进服时间: {get_data(first, 9)}"
            wx.TheClipboard.SetData(wx.TextDataObject(text))

        menu = wx.Menu()
        if len(selections) == 1:
            menu.Append(1, "复制详情")
            menu.Bind(wx.EVT_MENU, lambda _: copy_detail(), id=1)
            menu.Append(2, "查看逐小时在线分析")
            menu.Bind(wx.EVT_MENU, lambda _: self.open_hour_online_win(get_data(first, 1)), id=2)
            menu.Append(3, f"添加[{get_data(first, 1)}]至预览")
        else:
            menu.Append(3, f"添加[{len(selections)}]个玩家至预览")
        menu.Bind(wx.EVT_MENU, lambda _: self.add_players_to_preview(selections), id=3)
        self.PopupMenu(menu)

    def add_players_to_preview(self, selections: list[int]):
        event = AddPlayersOverviewEvent([self.player_info_lc.GetItemText(i, 1) for i in selections])
        event.SetEventObject(self)
        self.ProcessEvent(event)

    def open_hour_online_win(self, player: str):
        PlayerOnlineWin(self, player).Show()

    def on_filter_update(self, event: wx.Event):
        if event.GetEventObject() == self.reset_btn:
            day_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = timedelta(days=1) + day_start
            self.active_filter = OnlineTimeFilter(day_start.timestamp(), day_end.timestamp())
        else:
            if self.time_selector.hour_enable:
                r = self.time_selector.hour_enable = False
            else:
                r = True
            start, end = self.time_selector.get_time_range()
            start += timedelta(hours=self.time_selector.hour_ctrl.GetValue())
            end += timedelta(hours=self.time_selector.hour_ctrl.GetValue())
            self.active_filter = OnlineTimeFilter(start.timestamp(), end.timestamp())
            if not r:
                self.time_selector.hour_enable = True
        self.start_analyze(None)

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
        event = PlayerOnlineInfoEvent({name: info.online_times for name, info in players_info.items()})
        event.SetEventObject(self)
        self.ProcessEvent(event)
        self.populate_list(sorted_players_info)

    def populate_list(self, players_info: dict[str, PlayerOnlineInfo]):
        """填充玩家信息到列表控件"""
        self.player_info_lc.Freeze()
        self.player_info_lc.DeleteAllItems()
        for i, player_info, in enumerate(players_info.values()):
            self.add_player(player_info, i + 1)
        self.player_info_lc.Thaw()

    def add_player(self, player: PlayerOnlineInfo, rank: int):
        """添加一组信息进入列表"""
        line = self.player_info_lc.GetItemCount()
        self.player_info_lc.InsertItem(line, str(rank))
        self.player_info_lc.SetItem(line, 1, player.name)
        self.player_info_lc.SetItem(line, 2, string_fmt_time(player.total_online_time))
        self.player_info_lc.SetItem(line, 3, string_fmt_time(player.today_online_time))
        self.player_info_lc.SetItem(line, 4, string_fmt_time(player.avg_online_per_day))
        self.player_info_lc.SetItem(line, 5, str(len(player.online_times)))
        self.player_info_lc.SetItem(line, 6, string_fmt_time(player.avg_online_per_session))
        self.player_info_lc.SetItem(line, 7, string_fmt_time(player.max_online_per_session))
        self.player_info_lc.SetItem(line, 8, strftime("%y-%m-%d %H:%M:%S", localtime(player.last_offline_time)))
        self.player_info_lc.SetItem(line, 9, strftime("%y-%m-%d %H:%M:%S", localtime(player.join_server_time)))

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
            i = 0
            while i < len(info.online_times):
                start, end = info.online_times[i]
                if end - start < config.min_online_time:
                    # 如果在线时间小于min_online_time，检查是否可以与下一个时间段合并
                    if i + 1 < len(info.online_times) and info.online_times[i + 1][0] - end < config.min_online_time:
                        # 合并时间段
                        # noinspection PyUnusedLocal
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
            days = set()  # 计算玩家在线天数
            for start, end in info.online_times:
                dt_obj = datetime.fromtimestamp(start)
                days.add(str(dt_obj.date()))
            info.avg_online_per_day = info.total_online_time / len(days)  # 总时间 / 玩家在线天数

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
            match_times = []
            for start, stop in info.online_times:
                t = self.active_filter.filter((start, stop))
                if t:
                    match_times.append(t)
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
        if column == 0:
            return
        if self.sort_column == column:
            self.sort_ascending = not self.sort_ascending
        else:
            self.sort_column = column
            self.sort_ascending = True

        sorted_players_info = sort_players_info(self.activate_datas, column, self.sort_ascending)
        self.populate_list(sorted_players_info)
