from threading import Event
from time import time, perf_counter

from matplotlib import pyplot as plt
from matplotlib import rcParams as mpl_rcParams
from mcstatus import JavaServer
from mcstatus.status_response import JavaStatusResponse

from gui.about import AboutPanel
from gui.config import ConfigPanel
from gui.events import EVT_GET_STATUS_NOW, EVT_PAUSE_STATUS, EVT_SET_AS_OVERVIEW, SetAsOverviewEvent, \
    EVT_ADD_PLAYERS_OVERVIEW, AddPlayersOverviewEvent
from gui.overview import OverviewPanel, ServerStatus
from gui.players_info import PlayerPanel
from gui.status_plot import StatusPanel
from gui.widget import *
from lib.common_data import common_data
from lib.data import *
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


class NameTitle(CenteredText):
    def __init__(self, parent: wx.Window):
        super().__init__(parent, label=config.server_name)
        self.SetFont(ft(20))


def get_server_status_raw(use_ping: bool = True) -> ServerPoint | None:
    try:
        server = JavaServer.lookup(config.addr, timeout=config.time_out)
        status = server.status()
        ping = server.ping() if use_ping else 0
        point = translate_status(status, ping)
        return point
    except Exception as e:
        logger.warning(f"获取服务器状态失败: {e}")
        return None


def get_server_status_retry(use_ping: bool = True) -> ServerPoint | None:
    left_times = copy(config.retry_times)
    while True:
        point = get_server_status_raw(use_ping)
        if point is not None:
            return point
        else:
            left_times -= 1
            if left_times == 0:
                logger.error(f"重试[{config.retry_times}]次获取服务器状态后失败")
                return None
            else:
                logger.warning(f"尝试第[{config.retry_times - left_times}]次..")


class GUI(wx.Frame):
    def __init__(self):
        super().__init__(None, title=config.server_name + "监测", size=(1350, 850))
        logger.info("初始化GUI")
        self.data_manager = DataManager(config.data_dir)
        self.data_manager.load_data()
        common_data.data_manager = self.data_manager
        self.init_ui()
        self.server_status = ServerStatus.OFFLINE
        self.event_flag = Event()
        self.stop_flag = Event()
        self.time_reset_flag = Event()
        self.status_flag = Event()
        self.status_thread = Thread(target=self.status_thread_func)
        self.status_thread.start()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.status_flag.set()
        wx.CallLater(200, self.load_points_gui)

    def get_server_status(self) -> tuple[str, ServerPoint | None]:
        """
        返回值:
        ok -> 成功啦, Point
        event -> 有消息, None
        error -> 错误, None
        fp_error -> full players错误, Point
        fp_ok -> full players成功, Point
        """
        self.set_status(StatusStatus(ProgressStatus.STATUS))
        logger.debug("获取服务器状态")
        point = get_server_status_retry()
        if point is None or len(point.players) == point.online or (not config.enable_full_players):
            self.set_status(StatusStatus(ProgressStatus.WAIT))
            if point is None:
                return "error", None
            return "ok", point
        players = set()
        com_point = point.copy()
        fp_times = 0
        over_flag = 0
        while len(players) < com_point.online:
            self.set_status(StatusStatus(ProgressStatus.FP_STATUS, fp_times + 1, com_point.online - len(players)))
            now_point = get_server_status_retry(use_ping=False)
            self.set_status(StatusStatus(ProgressStatus.FP_WAIT, fp_times + 1, com_point.online - len(players)))
            if self.event_flag.is_set():
                return "event", None
            if com_point is None:
                logger.debug("完整玩家列表获取失败, 返回当前点数据")
                return "fp_error", point
            logger.debug(f"第{fp_times}次, 获取到玩家列表: {[p.name for p in now_point.players]}")

            if set(now_point.players) != set(com_point.players):
                com_point = now_point.copy()
                com_players = set(com_point.players)
                if com_point.online != point.online:  # 玩家数量发生变化
                    logger.debug(f"过程中玩家数量发生变化, 重置玩家列表 ({point.online}->{com_point.online})")
                    players = com_players
                    point.online = copy(com_point.online)
                    fp_times = 0
                else:
                    players |= com_players - players
                fp_times += 1
                over_flag = 0
            else:
                logger.debug("玩家列表无变化, 继续获取")
                over_flag += 1
                if over_flag > 4:
                    logger.debug("玩家列表无变化次数过多, 放弃获取完整玩家列表")
                    break

            if fp_times > config.fp_max_try:
                logger.debug(f"尝试次数过多(>{config.fp_max_try}), 放弃获取完整玩家列表")
                break
            self.event_flag.wait(timeout=config.fp_re_status_inv)
            if self.event_flag.is_set():
                return "event", None
        point.players = list(players)
        point.time = com_point.time
        logger.debug("完整玩家列表获取完成")
        self.set_status(StatusStatus(ProgressStatus.WAIT))
        return "fp_ok", point

    def on_close(self, _):
        logger.info("程序停止中...")
        self.data_manager.save_data()
        config.save()
        self.stop_flag.set()
        self.event_flag.set()
        self.status_thread.join()
        self.Destroy()
        logger.info("再见!")
        exit(0)

    def on_pause_status(self, _):
        self.status_flag.clear() if self.status_flag.is_set() else self.status_flag.set()
        self.event_flag.set()

    def load_points_gui(self):
        timer = Counter()
        timer.start()
        logger.info("加载点数据到GUI...")
        points = list(self.data_manager.points)

        self.status_panel.cap_list.points_init(points)
        self.status_panel.plot.points_init(points)
        if points:
            self.overview_panel.update_data([p.name for p in points[-1].players], points[-1].time, ServerStatus.ONLINE)
        else:
            self.overview_panel.update_data([], time(), ServerStatus.UNKNOWN)
        logger.info(f"GUI数据加载完成! (耗时: {timer.endT()})")

    # noinspection PyAttributeOutsideInit
    def init_ui(self):
        self.SetFont(ft(12))
        sizer = wx.BoxSizer(wx.VERTICAL)
        name_title = NameTitle(self)
        self.notebook = wx.Notebook(self)
        self.overview_panel = OverviewPanel(self.notebook)
        self.status_panel = StatusPanel(self.notebook)
        self.player_view_panel = PlayerPanel(self.notebook)
        self.config_panel = ConfigPanel(self.notebook)
        self.about_panel = AboutPanel(self.notebook)
        self.notebook.AddPage(self.overview_panel, "总览")
        self.notebook.AddPage(self.status_panel, "状态")
        self.notebook.AddPage(self.player_view_panel, "玩家")
        self.notebook.AddPage(self.config_panel, "设置")
        self.notebook.AddPage(self.about_panel, "关于")
        sizer.Add(name_title, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=5)
        sizer.Add(wx.StaticLine(self), flag=wx.EXPAND | wx.TOP | wx.BOTTOM, border=5)
        sizer.Add(self.notebook, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        self.SetSizer(sizer)

        name_title.SetMinSize((MAX_SIZE[0], 36))
        self.Bind(EVT_GET_STATUS_NOW, self.on_req_get_status)
        self.Bind(EVT_PAUSE_STATUS, self.on_pause_status)
        self.Bind(EVT_SET_AS_OVERVIEW, self.on_set_as_overview)
        self.Bind(EVT_ADD_PLAYERS_OVERVIEW, self.on_add_player_overview)
        self.notebook.SetMinSize(MAX_SIZE)
        self.SetBackgroundColour(self.status_panel.GetBackgroundColour())
        self.load_icon()
        self.Center()

    def on_add_player_overview(self, event: AddPlayersOverviewEvent):
        self.notebook.SetSelection(0)
        self.overview_panel.add_players(event.players)

    def on_set_as_overview(self, event: SetAsOverviewEvent):
        point = event.point
        self.notebook.SetSelection(0)
        self.overview_panel.update_data([p.name for p in point.players], point.time, ServerStatus.ONLINE)

    def load_icon(self):
        self.SetIcons(wx.IconBundle(f"assets/icon/icon.ico"))

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
                last_status = perf_counter()
                msg, point = self.get_server_status()
                if perf_counter() - last_status > config.check_inv:
                    last_status = last_status
                else:
                    last_status = perf_counter() - config.check_inv / 2
                if msg == ["ok", "error"]:
                    if point is not None:
                        self.data_manager.add_point(point)
                    wx.CallAfter(self.load_point, point)
                elif msg in ["fp_error", "fp_ok"]:
                    self.data_manager.add_point(point)
                    wx.CallAfter(self.load_point, point)

            self.event_flag.wait(1)
            if self.event_flag.is_set():
                self.event_flag.clear()
            if self.stop_flag.is_set():
                break
            elif self.time_reset_flag.is_set():
                last_status = 0
                self.time_reset_flag.clear()
                logger.info("用户请求立即获取状态")
            elif not self.status_flag.is_set():
                logger.info("状态线程已暂停")
                self.event_flag.wait()
                if self.status_flag.is_set():
                    logger.info("状态线程已恢复")
                    last_status = perf_counter()

    def load_point(self, point: ServerPoint | None):
        """在运行过程中 获取到的数据点 的加载函数"""
        if point:
            self.status_panel.plot.load_point(point, True)
            self.status_panel.cap_list.load_point(point, True)
            self.overview_panel.update_data([p.name for p in point.players], point.time, self.server_status)
        else:
            self.overview_panel.update_data([], time(), self.server_status)

    def set_status(self, status: StatusStatus):
        wx.CallAfter(self.status_panel.progress.set_status, status)
