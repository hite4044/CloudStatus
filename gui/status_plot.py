"""
状态面板
提供 在线人数图表 的GUI定义文件
"""
from bisect import bisect_right
from time import localtime, strftime, time, perf_counter

from matplotlib import pyplot as plt
from matplotlib import rcParams as mpl_rcParams
from matplotlib.backends import backend_wxagg as wxagg
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
from matplotlib.ticker import Formatter
from matplotlib.transforms import TransformedBbox

from gui.events import *
from gui.widget import *
from lib.common_data import common_data
from lib.data import *
from lib.perf import Counter

mpl_rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
ID_SELECT_ALL = wx.NewIdRef(count=1)

clamp = lambda x, a, b: max(min(x, b), a)


class UniqueIntFormatter(Formatter):
    def __init__(self):
        super().__init__()

    def format_ticks(self, values):
        # 只保留整数且唯一的值
        unique_ints = set(int(v) for v in values if v.is_integer())
        return [str(v)[:-2] if v in unique_ints else '' for v in values]


class StatusPanel(wx.SplitterWindow):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        sizer_l = wx.BoxSizer(wx.VERTICAL)
        self.left_panel = wx.Panel(self)
        self.data_jumper = DataJumper(self.left_panel)
        self.plot = Plot(self.left_panel)
        self.progress = ProgressShower(self.left_panel)

        border_width = 5
        sizer_l.Add(
            self.data_jumper,
            flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
            proportion=0,
            border=border_width,
        )
        sizer_l.Add(self.plot, flag=wx.EXPAND | wx.ALL, proportion=1, border=border_width)
        sizer_l.Add(
            self.progress,
            flag=wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT,
            proportion=0,
            border=border_width,
        )
        self.left_panel.SetSizer(sizer_l)

        self.cap_list = CapList(self)

        self.SplitVertically(self.left_panel, self.cap_list, 0)
        self.SetSashGravity(0.65)
        self.SetMinimumPaneSize(5)
        self.Bind(EVT_FILTER_CHANGE, self.on_filter_change)

    def on_filter_change(self, event: FilterChangeEvent):
        self.plot.update_filter(event.filter)


class CapList(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.data_manager = common_data.data_manager
        self.point_id_mapping: dict[int, str] = {}
        sizer = wx.BoxSizer(wx.VERTICAL)
        title = CenteredText(self, label="数据点列表")
        title.SetFont(ft(14))
        self.cap_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_VIRTUAL)
        self.cap_list.SetFont(ft(10))
        cols = [("序号", 55), ("时间", 115), ("延迟", 75), ("在线", 40), ("玩家", 150)]
        for i, (name, width) in enumerate(cols):
            if i == 4:
                self.cap_list.InsertColumn(i, name, width=wx.LIST_AUTOSIZE_USEHEADER, format=wx.LIST_FORMAT_LEFT)
                continue
            self.cap_list.InsertColumn(i + 1, name, width=width, format=wx.LIST_FORMAT_CENTRE)
        sizer.Add(title, flag=wx.EXPAND, proportion=0)
        sizer.Add(self.cap_list, flag=wx.EXPAND, proportion=1)
        self.SetSizer(sizer)

        self.Bind(wx.EVT_MENU, self.on_select_all, id=ID_SELECT_ALL)

        self.SetAcceleratorTable(
            wx.AcceleratorTable([wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("A"), ID_SELECT_ALL)])
        )
        self.line_height = 31
        self.cap_list.SetItemCount(10000)
        self.cap_list.OnGetItemText = self.OnGetItemText
        self.cap_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_item_menu)

    def OnGetItemText(self, item: int, col: int):
        pt = self.data_manager.get_point(self.point_id_mapping[item])
        if col == 0:
            return str(item + 1)
        elif col == 1:
            return strftime("%y-%m-%d %H:%M", localtime(pt.time))
        elif col == 2:
            return f"{pt.ping:.2f}ms"
        elif col == 3:
            return str(pt.online)
        elif col == 4:
            return ", ".join([p.name for p in pt.players])
        else:
            return ""

    def on_item_menu(self, event: wx.ListEvent):
        item = event.GetIndex()
        if item >= 0:
            def get_data(column: int):
                return self.cap_list.GetItem(item, column).GetText()
            def copy_data(column: int):
                wx.TheClipboard.SetData(wx.TextDataObject(get_data(column)))

            def copy_detail():
                text = f"ID: {get_data(0)}\n时间: {get_data(1)}\n在线: {get_data(3)}\n玩家们: "
                player_names = self.cap_list.GetItem(item, 4).GetText().split(", ")
                players = ""
                for i, player in enumerate(player_names):
                    if i == len(player_names) - 1:
                        players += f"{player}"
                    elif i % 3 == 2:
                        players += f"{player}\n"
                    else:
                        players += f"{player}, "
                text += players
                wx.TheClipboard.SetData(wx.TextDataObject(text))

            menu = wx.Menu()
            line: wx.MenuItem = menu.Append(-1, "复制详情")
            menu.Bind(wx.EVT_MENU, lambda e: copy_detail(), id=line.GetId())
            menu.AppendSeparator()
            line: wx.MenuItem = menu.Append(-1, "复制时间")
            menu.Bind(wx.EVT_MENU, lambda e: copy_data(1), id=line.GetId())
            line: wx.MenuItem = menu.Append(-1, "复制玩家列表")
            menu.Bind(wx.EVT_MENU, lambda e: copy_data(4), id=line.GetId())
            menu.AppendSeparator()
            line: wx.MenuItem = menu.Append(-1, "设为预览")
            menu.Bind(wx.EVT_MENU, lambda e: self.set_as_overview(item), id=line.GetId())
            line: wx.MenuItem = menu.Append(-1, "删除")
            menu.Bind(wx.EVT_MENU, lambda e: self.delete_item(item), id=line.GetId())
            self.PopupMenu(menu, event.GetPoint())
        else:
            event.Skip()

    def delete_item(self, item: int):
        point: ServerPoint = self.data_manager.get_point(self.point_id_mapping[item])
        self.data_manager.remove_point(point)
        self.point_id_mapping.pop(item)
        values = list(self.point_id_mapping.values())
        self.point_id_mapping.clear()
        self.point_id_mapping.update(enumerate(values))
        self.cap_list.SetItemCount(self.cap_list.GetItemCount() - 1)
        self.cap_list.Refresh()

    def set_as_overview(self, item: int):
        point: ServerPoint = self.data_manager.get_point(self.point_id_mapping[item])
        event = SetAsOverviewEvent(point)
        event.SetEventObject(self)
        self.ProcessEvent(event)

    def load_point(self, point: ServerPoint, runtime_add: bool = False):
        line = self.cap_list.GetItemCount()
        self.point_id_mapping[line] = point.id_
        self.cap_list.SetItemCount(line + 1)
        if runtime_add:
            self.cap_list.ScrollList(0, (line - 1) * self.line_height)

    def points_init(self, points: list[ServerPoint]):
        timer = Counter()
        timer.start()
        self.cap_list.SetItemCount(len(points))
        for i, point in enumerate(points):
            self.point_id_mapping[i] = point.id_
        logger.debug(f"数据点列表初始化用时: {timer.endT()}")
        self.cap_list.ScrollList(0, (self.cap_list.GetItemCount() - 1) * self.line_height)

    def on_select_all(self, _):
        for i in range(self.cap_list.GetItemCount()):
            self.cap_list.Select(i)


class DataJumper(wx.Panel):
    def __init__(self, parent: wx.Window, height: int = 29):
        super().__init__(parent)
        self.to_enable = False
        self.activate_filter = DataFilter()

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.enable_to_time_check = wx.CheckBox(self, label="启用范围选择")
        self.enable_to_time_check.SetMinSize((-1, height))
        self.from_time_ctrl = TimeSelector(self)
        self.sep_label = CenteredText(self, label="至")
        self.sep_label.SetMinSize((-1, height))
        self.to_time_ctrl = TimeSelector(self)
        self.load_btn = wx.Button(self, label="加载")
        self.reset_btn = wx.Button(self, label="重置")
        sizer.Add(self.enable_to_time_check, proportion=0)
        sizer.AddStretchSpacer()
        sizer.Add(self.from_time_ctrl, proportion=0)
        sizer.Add(self.sep_label, proportion=0, flag=wx.LEFT | wx.RIGHT, border=4)
        sizer.Add(self.to_time_ctrl, proportion=0)
        sizer.AddStretchSpacer()
        sizer.Add(self.load_btn, proportion=0)
        sizer.Add(self.reset_btn, proportion=0)
        self.SetSizer(sizer)

        self.to_time_ctrl.Hide()
        self.sep_label.Hide()
        self.load_btn.Bind(wx.EVT_BUTTON, self.update_filter)
        self.reset_btn.Bind(wx.EVT_BUTTON, self.reset_filter)
        self.enable_to_time_check.Bind(wx.EVT_CHECKBOX, self.check_enable_to)

    def check_enable_to(self, event: wx.Event):
        sizer: wx.BoxSizer = self.GetSizer()
        event.Skip()
        self.to_enable = self.enable_to_time_check.GetValue()
        if self.enable_to_time_check.GetValue():
            self.to_time_ctrl.Show()
            self.sep_label.Show()
        else:
            self.to_time_ctrl.Hide()
            self.sep_label.Hide()
        sizer.Layout()

    def update_filter(self, _):
        if self.to_enable:
            self.activate_filter = DataFilter(
                self.from_time_ctrl.get_time_range()[0].timestamp(),
                self.to_time_ctrl.get_time_range()[1].timestamp()
            )
        else:
            self.activate_filter = DataFilter(
                self.from_time_ctrl.get_time_range()[0].timestamp(),
                self.from_time_ctrl.get_time_range()[1].timestamp()
            )
        self.send_event()

    def reset_filter(self, _):
        self.activate_filter = DataFilter()
        self.send_event()

    def send_event(self):
        event = FilterChangeEvent(self.activate_filter)
        event.SetEventObject(self)
        self.ProcessEvent(event)


class Plot(wxagg.FigureCanvasWxAgg):
    """图表用于展示在线人数数据"""

    def __init__(self, parent: wx.Window):
        super().__init__(parent, wx.ID_ANY, Figure(tight_layout=True))
        self.activate_filter = DataFilter()

        axes = self.figure.gca()
        axes.set_title("在线人数")
        axes.set_xlabel("时间")
        axes.set_ylabel("在线人数")
        self.raw_datas: dict[float, ServerPoint] = {}
        self.datas: dict[float, ServerPoint] = {}
        self.showing_datas: dict[float, ServerPoint] = {}
        self.axes = axes
        self.offset: int = 0  # 当前显示的起始索引
        self.scale: float = 1.0  # 显示的数据占总数据的百分比
        self.start_drag: int = 0  # 拖动起始位置
        self.start_offset: int = 0  # 拖动开始时候的偏移量
        self.last_point_time = 0  # 上一个数据点的时间
        self.draw_call = wx.CallLater(50, self.draw_plot)
        self.draw_plot()
        self.Bind(wx.EVT_MOUSE_EVENTS, self.control_plot)
        self.tooltip = ToolTip(self, "")  # 创建工具提示

    def on_mouse_move(self, x: int, y: int):
        if not self.showing_datas:
            return
        if not self.GetScreenRect().Contains(x + self.GetScreenPosition()[0], y + self.GetScreenPosition()[1]):
            self.tooltip.set_tip("")
            return
        box: TransformedBbox = self.axes.get_window_extent()
        percent = (x - round(box.x0)) / (round(box.x1) - round(box.x0))
        if percent < 0 or percent > 1:
            self.tooltip.set_tip("")
            return
        times = sorted(self.showing_datas.keys())
        min_time = min(times)
        exact_time = (max(times) - min_time) * percent + min_time
        index = bisect_right(times, exact_time)
        closest_time = times[index - 1]
        point = self.showing_datas[closest_time]

        time_str = datetime.fromtimestamp(closest_time).strftime('%Y-%m-%d %H:%M:%S')
        players = ""
        for i, player in enumerate(point.players):
            if i == len(point.players) - 1:
                players += f"{player.name}"
            elif i % 3 == 2:
                players += f"{player.name}\n"
            else:
                players += f"{player.name}, "
        tooltip_text = f"""时间: {time_str}\n玩家: \n{players}"""
        self.tooltip.set_tip(tooltip_text)

    def update_filter(self, filter_: DataFilter):
        self.activate_filter = filter_
        self.datas = {p.time: p for p in filter_.filter_points(self.raw_datas)}  # 根据筛选条件更新数据
        if filter_.from_time is not None:
            self.scale = 1.0
            self.offset = 0
        if self.draw_call.IsRunning():
            self.draw_call.Restart()
        else:
            self.draw_call.Start()

    def control_plot(self, event: wx.MouseEvent):
        """
        滚轮缩放和拖动
        """
        event.Skip()
        if event.LeftDown():
            self.start_drag = event.GetX()
            self.start_offset = self.offset * 1
            self.tooltip.set_tip("")
            return
        elif event.Dragging():
            if self.start_drag == 0:
                return
            mouse_offset = (self.start_drag - event.GetX()) * self.scale / 2  # 考虑缩放比例
            self.offset = self.start_offset + int(mouse_offset / self.scale * 4)
        elif event.LeftUp():
            self.start_drag = self.start_offset = 0
            self.on_mouse_move(event.GetX(), event.GetY())
        elif event.GetWheelRotation():
            last_scale = self.scale + 1 - 1
            if event.GetWheelRotation() > 0:
                self.scale *= 0.9  # 放大
                self.offset += int(len(self.datas) * (last_scale - self.scale) / 2)
            else:
                self.scale *= 1.1  # 缩小
                self.offset -= int(len(self.datas) * (self.scale - last_scale) / 2)
        elif event.Moving():
            self.on_mouse_move(event.GetX(), event.GetY())
            return
        else:
            return
        self.offset = clamp(self.offset, 0, int(len(self.datas) * (1 - self.scale)))
        self.scale = clamp(self.scale, 0, 1)
        logger.debug(f"起始偏移: {self.offset}, 缩放: {self.scale}")
        self.draw_plot()

    def load_point(self, point: ServerPoint, runtime_add: bool = False):
        """
        添加数据点 (GUI层面)
        :param point: 数据点
        :param runtime_add: 是否为运行时添加, 以便自动滚动图表
        """
        before_length = len(self.datas)
        self.add_data(point)
        if self.draw_call.IsRunning():
            self.draw_call.Restart()
        elif runtime_add:
            self.draw_call.Start()
        if runtime_add:
            self.offset += len(self.datas) - before_length  # 自动滚动

    def add_data(self, point: ServerPoint, fix_add: bool = False):
        """
        添加数据点
        :param point: 数据点
        :param fix_add: 是否为间隔修复添加
        """
        if point.time >= self.last_point_time + config.fix_sep:
            self.add_data(point.copy(self.last_point_time + ((point.time - self.last_point_time) / 2)), fix_add=True)
        self.raw_datas[point.time] = point
        if self.activate_filter.check(point):
            self.datas[point.time] = point
        if not fix_add:
            self.last_point_time = point.time

    def points_init(self, points: list[ServerPoint]):
        """
        用数据点初始化图表
        :param points: 数据点列表
        """
        self.raw_datas = {p.time: p for p in points}
        self.datas = {p.time: p for p in points}
        self.last_point_time = points[-1].time if points else time()
        self.scale = 0.15
        self.offset = int(len(self.datas) * (1 - self.scale))
        self.draw_plot()

    def draw_plot(self):
        """
        根据目前数据绘制图表
        """
        if not self.datas:
            return
        self.axes.cla()
        self.axes.grid(True)
        start, stop = self.offset, self.offset + int(len(self.datas) * self.scale)
        self.showing_datas = slice_dict(self.datas, start, stop)
        if len(self.showing_datas) == 0:
            return
        self.axes.set_xlim(datetime.fromtimestamp(min(self.showing_datas.keys())),
                           datetime.fromtimestamp(max(self.showing_datas.keys())))
        self.axes.plot(
            [datetime.fromtimestamp(t) for t in self.showing_datas.keys()],
            [p.online for p in self.showing_datas.values()],
            color="#31AAC6", linewidth=1.5, alpha=0.8
        )
        self.axes.xaxis.set_major_formatter(DateFormatter('%d %H:%M'))
        self.axes.yaxis.set_major_formatter(UniqueIntFormatter())
        self.figure.canvas.draw()


class ProgressShower(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.info_text = FormatedText(self, fmt="下一次获取: {}后")
        self.pause_btn = wx.Button(self, label="暂停")
        self.get_status_btn = wx.Button(self, label="获取状态")
        self.progress_bar = wx.Gauge(self, range=114514)
        self.get_status_btn.SetMaxSize((-1, 29))
        self.get_status_btn.SetFont(ft(10))
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(self.info_text, flag=wx.EXPAND, proportion=1)
        top_sizer.Add(self.pause_btn, proportion=0)
        top_sizer.Add(self.get_status_btn, proportion=0)
        sizer.Add(top_sizer, flag=wx.EXPAND, proportion=0)
        sizer.Add(self.progress_bar, flag=wx.EXPAND, proportion=1)
        self.SetSizer(sizer)
        self.SetMinSize((-1, 55))
        self.SetMaxSize((-1, 55))

        self.pause_btn.Bind(wx.EVT_BUTTON, self.pause_btn_click)
        self.get_status_btn.Bind(wx.EVT_BUTTON, self.get_status_now)
        self.start_wait = perf_counter()
        self.status = StatusStatus(ProgressStatus.WAIT)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.progress_update, self.timer)
        self.timer.Start(490)

    def pause_btn_click(self, _):
        # 发送 暂停/恢复 事件
        event = PauseStatusEvent(not self.pause_btn.GetLabel() == "暂停")
        event.SetEventObject(self)
        self.ProcessEvent(event)
        if self.pause_btn.GetLabel() == "暂停":
            self.timer.Stop()
            self.get_status_btn.Enable(False)
            self.pause_btn.SetLabel("恢复")
            self.info_text.SetLabel("暂停中")
            self.info_text.SetBackgroundColour(wx.Colour((255, 242, 0)))
        else:
            self.get_status_btn.Enable(True)
            self.pause_btn.SetLabel("暂停")
            self.info_text.SetBackgroundColour(self.pause_btn.GetBackgroundColour())
            self.start_wait = perf_counter()
            self.info_text.fmt = "下一次获取: {}后"
            self.timer.Start(490)

    def get_status_now(self, _):
        # 发送 立即获取服务器信息 事件
        event = GetStatusNowEvent()
        event.SetEventObject(self)
        self.ProcessEvent(event)

        self.timer.Stop()
        self.progress_bar.Pulse()
        self.info_text.SetLabel("正在获取...")

    def progress_update(self, _):
        if self.status.status == ProgressStatus.WAIT:
            progress_percent = (perf_counter() - self.start_wait) / config.check_inv
            self.info_text.format(f"{config.check_inv - (perf_counter() - self.start_wait):.1f}秒")
        elif self.status.status == ProgressStatus.FP_WAIT:
            progress_percent = (perf_counter() - self.start_wait) / config.fp_re_status_inv
            self.info_text.format(f"{config.fp_re_status_inv - (perf_counter() - self.start_wait):.1f}秒")
        else:
            self.timer.Stop()
            return
        if progress_percent >= 1:
            self.timer.Stop()
        else:
            self.progress_bar.SetValue(int(progress_percent * 114514))

    def set_status(self, status: StatusStatus):
        self.status = status
        if status.status in [ProgressStatus.WAIT, ProgressStatus.FP_WAIT]:
            self.start_wait = perf_counter()
            self.timer.Start(490)
            if status.status == ProgressStatus.FP_WAIT:
                self.info_text.fmt = f"等待第{status.times}次获取玩家列表, 等待: {'{}'}, 剩余玩家: {status.players_left}"
            else:
                self.info_text.fmt = "下一次获取: {}后"
        elif status.status in [ProgressStatus.STATUS, ProgressStatus.FP_STATUS]:
            self.timer.Stop()
            self.progress_bar.Pulse()
            if status.status == ProgressStatus.FP_STATUS:
                self.info_text.SetLabel(f"第{status.times}次获取玩家列表...")
        elif status.status == ProgressStatus.PAUSE:
            self.timer.Stop()
            self.progress_bar.Pulse()
            self.info_text.SetLabel("暂停中")
            self.info_text.SetBackgroundColour(wx.Colour((255, 242, 0)))
            self.pause_btn.SetLabel("恢复")
            self.get_status_btn.Enable(False)
            return
