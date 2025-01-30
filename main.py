from datetime import datetime, time as dt_time, date as dt_date, timedelta
from threading import Event, Thread
from time import localtime, strftime, time, perf_counter

from matplotlib import pyplot as plt
from matplotlib import rcParams as mpl_rcParams
from matplotlib.backends import backend_wxagg as wxagg
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
from matplotlib.ticker import Formatter
from mcstatus import JavaServer
from mcstatus.status_response import JavaStatusResponse
from wx.adv import DatePickerCtrl

from data import *
from player_view import PlayerViewPanel
from widget import *

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


def translate_status(status: JavaStatusResponse, ping: float) -> ServerPoint:
    """
    将Java版服务器状态响应对象转换为ServerPoint对象。

    此函数负责解析给定的Java版服务器状态响应（status），并结合服务器的ping值，
    创建并返回一个ServerPoint对象，该对象包含了服务器的当前在线玩家数、玩家样本列表和ping值，
    以及记录这些数据的时间点。

    参数:
    - status: JavaStatusResponse对象，包含了服务器状态的详细信息。
    - ping: 浮点数，代表服务器的ping值，即网络延迟。

    返回:
    - ServerPoint对象，封装了记录时间、在线玩家数、玩家列表和ping值。
    """

    # 如果状态响应中的玩家列表存在，则直接使用；否则初始化为空列表
    raw_players = status.players.sample if status.players.sample else []

    # 通过列表推导式，将原始玩家样本列表中的每个玩家转换为Player对象
    players = [Player(p.name, p.id) for p in raw_players]

    # 创建并返回ServerPoint对象，包含当前时间、在线玩家数、玩家列表和ping值
    return ServerPoint(
        time(),
        status.players.online,
        players,
        ping,
    )


def get_server_status() -> ServerPoint | None:
    server = JavaServer.lookup(config.addr)
    try:
        logger.debug("获取服务器状态")
        status = server.status()
        ping = server.ping()
        point = translate_status(status, ping)
        return point
    except Exception as e:
        logger.error(f"获取服务器状态失败: {e}")
    return None


class GUI(wx.Frame):
    def __init__(self):
        super().__init__(None, title=config.server_name+"监测", size=(1350, 850))
        logger.info("初始化GUI")
        self.data_manager = DataManager("data")
        self.data_manager.load_data()
        self.init_ui()
        self.event_flag = Event()
        self.stop_flag = Event()
        self.time_reset_flag = Event()
        self.status_thread = Thread(target=self.status_thread_func)
        self.status_thread.start()
        wx.CallLater(200, self.load_points_gui)

    def load_points_gui(self):
        logger.info("加载点数据到GUI...")
        points = list(self.data_manager.points)

        self.status_panel.cap_list.points_init(points)
        self.status_panel.plot.points_init(points)
        logger.info("GUI数据加载完成!")

    # noinspection PyAttributeOutsideInit
    def init_ui(self):
        self.SetFont(ft(12))
        sizer = wx.BoxSizer(wx.VERTICAL)
        name_title = NameTitle(self)
        self.notebook = wx.Notebook(self)
        self.status_panel = StatusPanel(self.notebook)
        self.player_view_panel = PlayerViewPanel(self.notebook, self.data_manager)
        self.notebook.AddPage(self.status_panel, "状态")
        self.notebook.AddPage(self.player_view_panel, "玩家")
        sizer.Add(name_title, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=5)
        sizer.Add(wx.StaticLine(self), flag=wx.EXPAND | wx.TOP | wx.BOTTOM, border=5)
        sizer.Add(self.notebook, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        self.SetSizer(sizer)

        name_title.SetMinSize((MAX_SIZE[0], 36))
        self.notebook.SetMinSize(MAX_SIZE)
        self.SetBackgroundColour(self.status_panel.GetBackgroundColour())
        self.Center()

    def status_thread_func(self):
        logger.info("状态记录线程已启动")
        last_status = perf_counter()
        while True:
            during = perf_counter() - last_status
            if during >= config.check_inv:
                status = get_server_status()
                last_status = perf_counter()
                if status:
                    self.data_manager.add_point(status)
                    logger.debug("数据获取成功")
                wx.CallAfter(self.load_point, status)
            self.event_flag.wait(1)
            if self.stop_flag.is_set():
                break
            elif self.time_reset_flag.is_set():
                last_status = 0
                self.time_reset_flag.clear()
                self.event_flag.clear()
                logger.info("用户请求立即获取状态")

    def load_point(self, point: ServerPoint | None):
        if point:
            self.status_panel.plot.load_point(point, True)
            self.status_panel.cap_list.load_point(point, True)
        self.status_panel.progress.load_point(point)


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

        self.right_panel = wx.Panel(self)
        sizer_r = wx.BoxSizer(wx.VERTICAL)
        self.config_panel = ConfigPanel(self.right_panel)
        self.cap_list = CapList(self.right_panel)

        sizer_r.Add(self.config_panel, flag=wx.EXPAND | wx.TOP | wx.RIGHT, proportion=0, border=5)
        sizer_r.Add(self.cap_list, flag=wx.EXPAND | wx.BOTTOM | wx.RIGHT, proportion=1, border=5)
        self.right_panel.SetSizer(sizer_r)

        self.SplitVertically(self.left_panel, self.right_panel, 0)
        self.SetSashGravity(0.65)
        self.Bind(EVT_FILTER_CHANGE, self.on_filter_change)

    def on_filter_change(self, event: FilterChangeEvent):
        self.plot.update_filter(event.filter)


class NameTitle(CenteredStaticText):
    def __init__(self, parent: wx.Window):
        super().__init__(parent, label=config.server_name)
        self.SetFont(ft(20))


class ConfigPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.config_map = {
            "addr": ["地址", str, config.addr],
            "check_inv": ["检查间隔", float, config.check_inv],
            "points_per_file": ["点/文件", int, config.points_per_file],
            "saved_per_points": ["点/保存", int, config.saved_per_points],
            "max_plot_points": ["最大绘图点数", int, config.max_plot_points],
            "min_online_time": ["最小在线时间", int, config.min_online_time],
            "fix_sep": ["数据空隙修复间隔", float, config.fix_sep],
        }
        title = CenteredStaticText(self, label="配置")
        title.SetFont(ft(14))
        sizer.Add(title, flag=wx.EXPAND, proportion=0)
        self.SetFont(ft(11))
        for key, (label, fmt, value) in self.config_map.items():
            line = ConfigLine(self, label, value, fmt, key, config.set_value)
            sizer.Add(line, flag=wx.EXPAND, proportion=0)
            sizer.AddSpacer(2)
        self.SetFont(ft(12))
        self.SetSizer(sizer)


class CapList(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        title = CenteredStaticText(self, label="状态列表")
        title.SetFont(ft(14))
        self.cap_list = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.cap_list.SetFont(ft(10))
        cols = [("序号", 55), ("时间", 115), ("在线", 40), ("玩家", 150), ("延迟", 75)]
        for i, (name, width) in enumerate(cols):
            if i == 3:
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
        self.cap_list.InsertItem(0, "Get Line Height")
        self.line_height = self.cap_list.GetItemRect(0).height
        self.cap_list.DeleteItem(0)

    def load_point(self, point: ServerPoint, runtime_add: bool = False):
        line = self.cap_list.GetItemCount()
        self.cap_list.InsertItem(line, str(line + 1))
        self.cap_list.SetItem(line, 1, strftime("%y-%m-%d %H:%M", localtime(point.time)))
        self.cap_list.SetItem(line, 2, str(point.online))
        self.cap_list.SetItem(line, 3, ", ".join([p.name for p in point.players]))
        self.cap_list.SetItem(line, 4, f"{point.ping:.2f}ms")
        if runtime_add:
            self.cap_list.ScrollList(0, (line - 1) * self.line_height)

    def points_init(self, points: list[ServerPoint]):
        for point in points[:-1]:
            self.load_point(point)
        self.cap_list.ScrollList(0, (self.cap_list.GetItemCount() - 1) * self.line_height)

    def on_select_all(self, _):
        for i in range(self.cap_list.GetItemCount()):
            self.cap_list.Select(i)


class TimeSelector(wx.Panel):
    def __init__(self, parent: wx.Window, height: int = 29):
        super().__init__(parent)
        self.hour_enable = False

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        label = CenteredStaticText(self, label="日期: ")
        label.SetMinSize((-1, height))
        self.date_ctrl = DatePickerCtrl(self, size=(115, height))
        self.enable_hour_check = wx.CheckBox(self)
        self.enable_hour_check.SetMinSize((-1, height))
        self.label_hour = CenteredStaticText(self, label="时: ")
        self.label_hour.SetMinSize((-1, height))
        self.hour_ctrl = wx.SpinCtrl(self, size=(50, height), min=0, max=23)
        sizer.Add(label, proportion=0)
        sizer.Add(self.date_ctrl, proportion=0)
        sizer.Add(self.enable_hour_check, proportion=0)
        sizer.Add(self.label_hour, proportion=0)
        sizer.Add(self.hour_ctrl, proportion=0)
        self.SetSizer(sizer)

        self.hour_ctrl.Hide()
        self.label_hour.Hide()
        self.enable_hour_check.Bind(wx.EVT_CHECKBOX, self.check_enable_hour)

    def check_enable_hour(self, event: wx.Event):
        sizer: wx.BoxSizer = self.GetSizer()
        event.Skip()
        self.hour_enable = self.enable_hour_check.GetValue()
        if self.enable_hour_check.GetValue():
            self.label_hour.Show()
            self.hour_ctrl.Show()
        else:
            self.label_hour.Hide()
            self.hour_ctrl.Hide()
        sizer.Layout()
        self.GetParent().GetSizer().Layout()

    def get_time_point(self) -> datetime:
        wx_date: wx.DateTime = self.date_ctrl.GetValue()
        date = dt_date(year=wx_date.GetYear(), month=wx_date.GetMonth() + 1, day=wx_date.GetDay())
        time_ = dt_time(hour=self.hour_ctrl.GetValue()) if self.hour_enable else dt_time()
        return datetime.combine(date, time_)

    def get_time_range(self) -> tuple[datetime, datetime]:
        correct = self.get_time_point()
        if self.hour_enable:
            return correct, correct + timedelta(hours=1)
        else:
            return correct, correct + timedelta(days=1)


class DataJumper(wx.Panel):
    def __init__(self, parent: wx.Window, height: int = 29):
        super().__init__(parent)
        self.to_enable = False
        self.activate_filter = DataFilter()

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.enable_to_time_check = wx.CheckBox(self, label="启用范围选择")
        self.enable_to_time_check.SetMinSize((-1, height))
        self.from_time_ctrl = TimeSelector(self)
        self.sep_label = CenteredStaticText(self, label="至")
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
        super().__init__(parent, wx.ID_ANY, Figure())
        self.activate_filter = DataFilter()

        axes = self.figure.gca()
        axes.set_title("在线人数")
        axes.set_xlabel("时间")
        axes.set_ylabel("在线人数")
        self.raw_datas: dict[float, ServerPoint] = {time(): ServerPoint(time(), 0, [], 0)}
        self.datas: dict[float, ServerPoint] = {time(): ServerPoint(time(), 0, [], 0)}
        self.axes = axes
        self.offset: int = 0  # 当前显示的起始索引
        self.scale: float = 1.0  # 显示的数据占总数据的百分比
        self.start_drag: int = 0  # 拖动起始位置
        self.start_offset: int = 0  # 拖动开始时候的偏移量
        self.last_point_time = 0  # 上一个数据点的时间
        self.draw_call = wx.CallLater(50, self.draw_plot)
        self.draw_plot()
        self.Bind(wx.EVT_MOUSE_EVENTS, self.control_plot)

    def update_filter(self, filter_: DataFilter):
        self.activate_filter = filter_
        self.datas = {p.time:p for p in filter_.filter_points(self.raw_datas)}  # 根据筛选条件更新数据
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
            return
        elif event.Dragging():
            if self.start_drag == 0:
                return
            mouse_offset = (self.start_drag - event.GetX()) * self.scale / 2  # 考虑缩放比例
            self.offset = self.start_offset + int(mouse_offset / self.scale)
        elif event.GetWheelRotation():
            last_scale = self.scale + 1 - 1
            if event.GetWheelRotation() > 0:
                self.scale *= 0.9  # 放大
                self.offset += int(len(self.datas) * (last_scale - self.scale) / 2)
            else:
                self.scale *= 1.1  # 缩小
                self.offset -= int(len(self.datas) * (self.scale - last_scale) / 2)
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
        if len(self.datas) > config.max_plot_points:
            self.datas.pop(min(self.datas.keys()))
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
        self.axes.cla()
        self.axes.grid(True)
        start, stop = self.offset, self.offset + int(len(self.datas) * self.scale)
        visible_datas = slice_dict(self.datas, start, stop)
        self.axes.plot(
            [datetime.fromtimestamp(t) for t in visible_datas.keys()],
            [p.online for p in visible_datas.values()],
            color="#31AAC6", linewidth=2, alpha=0.8
        )
        self.axes.xaxis.set_major_formatter(DateFormatter('%d %H:%M'))
        self.axes.yaxis.set_major_formatter(UniqueIntFormatter())
        self.figure.canvas.draw()



class ProgressShower(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.info_text = FormatedText(self, fmt="下一次获取: {}后")
        self.get_status_btn = wx.Button(self, label="获取状态")
        self.progress_bar = wx.Gauge(self, range=100, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.get_status_btn.SetMaxSize((-1, 29))
        self.get_status_btn.SetFont(ft(10))
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        top_sizer.Add(self.info_text, flag=wx.EXPAND, proportion=1)
        top_sizer.Add(self.get_status_btn, proportion=0)
        sizer.Add(top_sizer, flag=wx.EXPAND, proportion=0)
        sizer.Add(self.progress_bar, flag=wx.EXPAND, proportion=1)
        self.SetSizer(sizer)
        self.SetMinSize((-1, 55))
        self.SetMaxSize((-1, 55))

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.progress_update, self.timer)
        self.get_status_btn.Bind(wx.EVT_BUTTON, self.get_status_now)
        self.timer.Start(490)
        self.start_wait = perf_counter()

    def get_status_now(self, _):
        gui.time_reset_flag.set()
        gui.event_flag.set()

        self.timer.Stop()
        self.progress_bar.Pulse()
        self.info_text.SetLabel("正在获取...")

    def progress_update(self, _):
        progress_percent = (perf_counter() - self.start_wait) / config.check_inv
        if progress_percent >= 1:
            self.timer.Stop()
            self.progress_bar.Pulse()
            self.info_text.SetLabel("正在获取...")
        else:
            self.progress_bar.SetValue(int(progress_percent * 100))
            self.info_text.format(f"{config.check_inv - (perf_counter() - self.start_wait):.1f}秒")

    def load_point(self, _):
        self.start_wait = perf_counter()
        self.timer.Start()


if __name__ == "__main__":
    app = wx.App()
    gui = GUI()
    logger.info("布局窗口")
    gui.Show()
    logger.info("加载完成！")
    try:
        app.MainLoop()
    except KeyboardInterrupt:
        pass
    gui.stop_flag.set()
    config.save()
    gui.data_manager.save_data()
    gui.status_thread.join()
