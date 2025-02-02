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

from gui.config import ConfigPanel
from gui.events import EVT_GET_STATUS_NOW
from lib.data import *
from gui.widget import *
from gui.player_view import PlayerPanel
from gui.status import StatusPanel
from lib.perf import Counter

mpl_rcParams["font.family"] = "Microsoft YaHei"
plt.rcParams["axes.unicode_minus"] = False
ID_SELECT_ALL = wx.NewIdRef(count=1)


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


class NameTitle(CenteredStaticText):
    def __init__(self, parent: wx.Window):
        super().__init__(parent, label=config.server_name)
        self.SetFont(ft(20))


class GUI(wx.Frame):
    def __init__(self):
        super().__init__(None, title=config.server_name + "监测", size=(1350, 850))
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
        timer = Counter()
        timer.start()
        logger.info("加载点数据到GUI...")
        points = list(self.data_manager.points)

        self.status_panel.cap_list.points_init(points)
        self.status_panel.plot.points_init(points)
        logger.info(f"GUI数据加载完成! (耗时: {timer.endT()})")

    # noinspection PyAttributeOutsideInit
    def init_ui(self):
        self.SetFont(ft(12))
        sizer = wx.BoxSizer(wx.VERTICAL)
        name_title = NameTitle(self)
        self.notebook = wx.Notebook(self)
        self.status_panel = StatusPanel(self.notebook)
        self.player_view_panel = PlayerPanel(self.notebook, self.data_manager)
        self.config_panel = ConfigPanel(self.notebook)
        self.notebook.AddPage(self.status_panel, "状态")
        self.notebook.AddPage(self.player_view_panel, "玩家")
        self.notebook.AddPage(self.config_panel, "配置")
        sizer.Add(name_title, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=5)
        sizer.Add(wx.StaticLine(self), flag=wx.EXPAND | wx.TOP | wx.BOTTOM, border=5)
        sizer.Add(self.notebook, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        self.SetSizer(sizer)

        name_title.SetMinSize((MAX_SIZE[0], 36))
        self.Bind(EVT_GET_STATUS_NOW, self.on_req_get_status)
        self.notebook.SetMinSize(MAX_SIZE)
        self.SetBackgroundColour(self.status_panel.GetBackgroundColour())
        self.Center()

    def on_req_get_status(self, _):
        self.time_reset_flag.set()
        self.event_flag.set()

    def status_thread_func(self):
        """获取状态线程 的绑定函数"""
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
        """在运行过程中 获取到的数据点 的加载函数"""
        if point:
            self.status_panel.plot.load_point(point, True)
            self.status_panel.cap_list.load_point(point, True)
        self.status_panel.progress.load_point(point)


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
