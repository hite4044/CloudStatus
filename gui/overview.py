"""
预览面板
提供 服务器预览 的GUI定义文件
"""
from threading import Thread
from time import strftime, localtime

from gui.events import GetStatusNowEvent, AskToAddPlayerEvent, EVT_ASK_TO_ADD_PLAYER, RemovePlayerOverviewEvent, \
    EVT_REMOVE_PLAYER_OVERVIEW
from gui.online_widget import PlayerOnlineWin
from gui.widget import *
from lib.color_picker import get_player_color
from lib.common_data import common_data
from lib.config import config
from lib.data import ServerPoint, Player
from lib.log import logger
from lib.skin import skin_mgr, HeadLoadData

MAX_HAP = 20
MIN_HAP = 6


class ServerStatus(Enum):
    ONLINE = 0
    OFFLINE = 1
    UNKNOWN = 2


class NameLabel(CenteredText):
    """玩家名称Label (封装了渐变色)"""

    def __init__(self, parent: wx.Window, label: str, size=wx.DefaultSize):
        super().__init__(parent, label=label, size=size)
        self.bg_binder = GradientBgBinder(self)
        self.bg_binder.set_color(self.GetBackgroundColour())
        self.set_best_font_size()

    def set_color(self, color: wx.Colour, color2: wx.Colour = wx.NullColour):
        self.bg_binder.set_color(color, color2)

    def set_best_font_size(self):
        dc = wx.ClientDC(self)
        ft_size = 18
        while True:
            dc.SetFont(ft(ft_size))
            size = dc.GetTextExtent(self.GetLabel())
            if size[0] > 180:
                ft_size -= 1
            else:
                break
        self.SetFont(ft(ft_size))


class PlayerHead(CenteredBitmap):
    """玩家头像 (封装了渐变色)"""

    def __init__(self, parent: wx.Window):
        super().__init__(parent, size=(88, 88))
        self.bg_binder = GradientBgBinder(self)
        self.bg_binder.set_color(self.GetBackgroundColour())

    def set_color(self, color: wx.Colour, color2: wx.Colour = wx.NullColour):
        self.bg_binder.set_color(color, color2)


class PlayerCard(wx.Panel):
    """玩家名称Label (封装了渐变色)"""

    def __init__(self, parent: wx.Window, name: str):
        wx.Panel.__init__(self, parent, size=(180, 180))
        self.player = name
        self.head_image = None
        self.head = PlayerHead(self)
        self.name_label = NameLabel(self, label=name, size=(-1, 32))
        Thread(target=self.load_head, daemon=True).start()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.head, flag=wx.EXPAND, proportion=1)
        sizer.Add(self.name_label, flag=wx.EXPAND, proportion=0)
        self.SetSizer(sizer)
        self.head.Bind(wx.EVT_RIGHT_UP, self.on_menu_click)

    def on_menu_click(self, _):
        menu = wx.Menu()
        menu.Append(wx.ID_ADD, "添加玩家")
        menu.AppendSeparator()
        menu.Append(wx.ID_INFO, "打开玩家信息")
        menu.Append(wx.ID_COPY, "复制名字")
        menu.Append(wx.ID_REFRESH, "刷新头像")
        menu.AppendSeparator()
        menu.Append(wx.ID_DELETE, "删除玩家")
        menu.Bind(wx.EVT_MENU, lambda _: self.ProcessEvent(AskToAddPlayerEvent()), id=wx.ID_ADD)
        menu.Bind(wx.EVT_MENU, lambda _: PlayerOnlineWin(self, self.player).Show(), id=wx.ID_INFO)
        menu.Bind(wx.EVT_MENU, lambda _: wx.TheClipboard.SetData(wx.TextDataObject(self.player)), id=wx.ID_COPY)
        menu.Bind(wx.EVT_MENU, self.refresh_head, id=wx.ID_REFRESH)
        menu.Bind(wx.EVT_MENU, lambda _: self.ProcessEvent(RemovePlayerOverviewEvent(self.player)), id=wx.ID_DELETE)
        self.PopupMenu(menu)
        menu.Destroy()

    def refresh_head(self, *_):
        logger.info("刷新头像")
        Thread(target=self.load_head, args=(False,), daemon=True).start()

    def load_card_color(self, head: Image.Image):
        """从玩家头像中提取两个眼睛的颜色并应用到控件中"""
        left_eye, right_eye = get_player_color(head, config.player_card_pick_way)
        color_left, color_right = EasyColor(*left_eye), EasyColor(*right_eye)

        # 亮度向增加30%, 饱和度减少25%
        lum_target, lum_percent = 1.0, 0.3
        color_left.lum = color_left.lum * (1 - lum_percent) + lum_target * lum_percent
        color_right.lum = color_right.lum * (1 - lum_percent) + lum_target * lum_percent
        sat_target, sat_percent = 0.0, 0.25
        color_left.sat = color_left.sat * (1 - sat_percent) + sat_target * sat_percent
        color_right.sat = color_right.sat * (1 - sat_percent) + sat_target * sat_percent

        self.head.set_color(color_left.wxcolor, color_right.wxcolor)
        self.name_label.set_color(color_left.add_luminance(0.1).wxcolor, color_right.add_luminance(0.1).wxcolor)
        self.Refresh()

    def load_head(self, use_cache: bool = True):
        head = skin_mgr.get_player_head(HeadLoadData(Player(self.player), 80, use_cache=use_cache))[1]
        try:
            self.head.SetBitmap(PilImg2WxImg(head))
        except RuntimeError:
            logger.error("无法更新玩家头像 -> 控件已销毁")
            return
        self.load_card_color(head)
        self.head_image = head
        wx.CallAfter(self.Layout)


class PlayerCardList(wx.ScrolledWindow):
    """装一堆玩家卡片的列表"""

    def __init__(self, parent: wx.Window):
        self.old_hgap = 20
        self.old_cols = 10
        wx.ScrolledWindow.__init__(self, parent)
        self.cards: dict[str, PlayerCard] = {}
        self.sizer = wx.FlexGridSizer(rows=0, cols=10, vgap=16, hgap=20)
        self.SetSizer(self.sizer)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_RIGHT_DOWN, self.on_menu)
        self.Bind(EVT_ASK_TO_ADD_PLAYER, self.on_add_player)
        self.Bind(EVT_REMOVE_PLAYER_OVERVIEW, self.on_remove_player)
        self.SetVirtualSize(1316, 630)
        self.SetScrollRate(0, 20)

    def on_card_open(self, event: wx.MouseEvent):
        """当双击玩家卡片"""
        card: PlayerCard = event.GetEventObject().GetParent()
        if card.player in self.cards:
            PlayerOnlineWin(self, card.player).Show()

    def on_remove_player(self, event: RemovePlayerOverviewEvent):
        self.sizer.Detach(self.cards[event.player])
        card = self.cards.pop(event.player)
        card.Destroy()

    def on_clear_all_cards(self, _):
        ret = wx.MessageBox("你真的想要清空列表吗?", "警告", wx.YES_NO | wx.ICON_WARNING, self)
        if ret != wx.YES:
            return
        for card in self.cards.values():
            self.sizer.Detach(card)
            card.Destroy()
        self.cards.clear()

    def on_menu(self, _):
        menu = wx.Menu()
        menu.Append(wx.ID_ADD, "添加玩家")
        menu.Append(wx.ID_REFRESH, "刷新所有头像颜色")
        menu.Append(wx.ID_CLEAR, "清空列表")
        menu.Bind(wx.EVT_MENU, self.on_add_player, id=wx.ID_ADD)
        menu.Bind(wx.EVT_MENU, self.update_all_player_color, id=wx.ID_REFRESH)
        menu.Bind(wx.EVT_MENU, self.on_clear_all_cards, id=wx.ID_CLEAR)
        self.PopupMenu(menu)
        menu.Destroy()

    def update_all_player_color(self, _):
        dialog = wx.ProgressDialog("更新玩家头像颜色", "正在更新...", len(self.cards), self)
        for i, card in enumerate(self.cards.values()):
            if card.head_image is None:
                continue
            dialog.Update(i)
            card.load_card_color(card.head_image)
        dialog.Destroy()

    def update_players(self, players: list[str]) -> None:
        """更新其中的玩家"""
        for card in self.cards.values():
            self.sizer.Detach(card)
            card.Destroy()
        self.cards.clear()
        for player in players:
            card = PlayerCard(self, player)
            card.head.Bind(wx.EVT_LEFT_DCLICK, self.on_card_open)
            self.cards[player] = card
            self.sizer.Add(card, flag=wx.EXPAND)
        self.on_size(None)
        self.Refresh()

    def on_add_player(self, event: AskToAddPlayerEvent):
        event.Skip()
        player_dialog = wx.TextEntryDialog(self, "玩家名称: ", "添加玩家")
        if player_dialog.ShowModal() == wx.ID_OK:
            player = player_dialog.GetValue()
            if player not in self.cards:
                self.add_players([player])

    def on_size(self, _):
        width = self.GetSize()[0]
        self.SetVirtualSize(width, (len(self.cards) // self.old_cols + 1) * (
                180 + self.sizer.GetHGap()) - self.sizer.GetHGap())  # (每卡片高度+卡片间距)*卡片行数-卡片间距
        now_cols = int(width / 185)
        if now_cols > 1:  # (窗口宽度-卡片宽度和)/卡片列数
            now_hgap = max(MIN_HAP, min(MAX_HAP, (self.GetSize()[0] - (now_cols * 180)) // (now_cols - 1)))
        else:  # 处理宽度极小的情况
            now_hgap = 5
            now_cols = 1
        if self.old_hgap != now_hgap and now_cols <= len(self.cards):
            self.sizer.SetHGap(now_hgap)
            self.sizer.Layout()
            self.old_hgap = now_hgap
        if now_cols != self.old_cols:
            self.sizer.SetCols(now_cols)
            self.sizer.Layout()
            self.old_cols = now_cols

    def add_players(self, players: list[str]):
        for player in players:
            if player not in self.cards:
                card = PlayerCard(self, player)
                card.head.Bind(wx.EVT_LEFT_DCLICK, self.on_card_open)
                self.cards[player] = card
                self.sizer.Add(card, flag=wx.EXPAND)
        self.on_size(None)


class PlayerOnlineOverviewPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.activate_total_players = []
        self.activate_today_players = []
        self.activate_active_players = []
        self.data_manager = common_data.data_manager
        self.today_calc_way: int = config.today_player_calc_way
        self.custom_hours: int = config.tcw_custom_hours
        self.custom_start: int = config.tcw_custom_start

        self.total_players = LabeledData(self, label="玩家总数", data="0")
        self.today_players = LabeledData(self, label="今日在线", data="0")
        self.active_players = LabeledData(self, label="活跃人数", data="0")
        self.total_online_time = LabeledData(self, label="总在线时长", data="0")
        sizer = wx.GridSizer(1, 4, 10, 10)
        sizer.Add(self.total_players, flag=wx.EXPAND)
        sizer.Add(self.today_players, flag=wx.EXPAND)
        sizer.Add(self.active_players, flag=wx.EXPAND)
        sizer.Add(self.total_online_time, flag=wx.EXPAND)
        self.SetSizer(sizer)

        timer = wx.Timer(self)
        timer.Bind(wx.EVT_TIMER, self.update_data)
        timer.Start(60 * 1000)
        self.update_data()
        self.total_players.Bind(wx.EVT_LEFT_DCLICK, self.total_players_cbk)
        self.today_players.Bind(wx.EVT_LEFT_DCLICK, self.today_players_cbk)
        self.active_players.Bind(wx.EVT_LEFT_DCLICK, self.active_players_cbk)
        self.today_players.Bind(wx.EVT_RIGHT_DOWN, self.on_today_player_menu)

    def total_players_cbk(self, _):
        dialog = DataShowDialog(self, self.activate_total_players, "玩家", "所有玩家")
        dialog.ShowModal()

    def today_players_cbk(self, _):
        dialog = DataShowDialog(self, self.activate_today_players, "玩家", "今日在线玩家")
        dialog.ShowModal()

    def on_today_player_menu(self, _):
        menu = wx.Menu()
        menu.Append(0, "先前24小时以来", kind=wx.ITEM_CHECK)
        menu.Append(1, "今天0点以来", kind=wx.ITEM_CHECK)
        menu.Append(2, f"先前{self.custom_hours}小时以来 (自定义)", kind=wx.ITEM_CHECK)
        menu.Append(3, f"今天{self.custom_start}点以来 (自定义)", kind=wx.ITEM_CHECK)
        menu.Check(self.today_calc_way, True)
        menu.Bind(wx.EVT_MENU, self.menu_cbk)
        self.PopupMenu(menu)

    def menu_cbk(self, event: wx.CommandEvent):
        if event.GetId() == 2:
            dialog = wx.NumberEntryDialog(self, "自定义小时-先前x小时以来", "请输入小时数", "小时数", 24, 1, 1000)
            if dialog.ShowModal() == wx.ID_OK:
                self.custom_hours = config.tcw_custom_hours = dialog.GetValue()
            else:
                return
        elif event.GetId() == 3:
            dialog = wx.NumberEntryDialog(self, "自定义小时-今天x点以来", "请输入小时", "小时", 4, 1, 24)
            if dialog.ShowModal() == wx.ID_OK:
                self.custom_start = config.tcw_custom_start = dialog.GetValue()
            else:
                return
        self.today_calc_way = config.today_player_calc_way = event.GetId()
        self.update_data()

    def active_players_cbk(self, _):
        dialog = DataShowDialog(self, self.activate_active_players, "玩家", "活跃玩家")
        dialog.ShowModal()

    def update_data(self, *_):
        ranges = self.data_manager.get_all_online_ranges().items()

        total_players = set()
        for pt in self.data_manager.points:
            for player in pt.players:
                total_players.add(player.name)
        self.total_players.SetData(str(len(total_players)))

        day_end = datetime.now().timestamp()
        if self.today_calc_way == 0:
            day_start = (datetime.now() - timedelta(days=1))
        elif self.today_calc_way == 1:
            day_start = datetime.combine(datetime.now().date(), datetime.min.time())
        elif self.today_calc_way == 2:
            day_start = datetime.now() - timedelta(hours=self.custom_hours)
        else:
            day_start = datetime.combine(datetime.now().date(), datetime.min.time().replace(hour=self.custom_start))
        day_start = day_start.timestamp()
        today_players = set()
        total_online_time = 0
        for player, times in ranges:
            for start, end in times:
                if day_start <= start <= day_end or day_start <= end <= day_end:
                    today_players.add(player)
                total_online_time += end - start
        self.today_players.SetData(str(len(today_players)))
        self.total_online_time.SetData(string_fmt_time(total_online_time))

        active_players_day: dict[str, set[str]] = {}
        seven_days_ago = datetime.now() - timedelta(days=7)
        for player, times in ranges:
            for start, end in times:
                start = datetime.fromtimestamp(start)
                end = datetime.fromtimestamp(end)
                if player not in active_players_day:
                    active_players_day[player] = set()
                if end > seven_days_ago:
                    active_players_day[player].add(end.strftime("%Y-%m-%d"))
                elif start > seven_days_ago:
                    active_players_day[player].add(start.strftime("%Y-%m-%d"))
        new_active_players_day = {}
        for player, days in active_players_day.items():
            if len(days) >= 4:
                new_active_players_day[player] = days
        self.active_players.SetData(str(len(new_active_players_day)))

        self.activate_total_players = list(total_players)
        self.activate_today_players = list(today_players)
        self.activate_active_players = list(new_active_players_day.keys())


class OverviewPanel(wx.Panel):
    """预览面板, 相当于地基"""

    def __init__(self, parent: wx.Window):
        wx.Panel.__init__(self, parent)
        self.data_manager = common_data.data_manager
        self.time_label = CenteredText(self, label="时间: 2025-02-14 21:51:39")
        self.reset_btn = wx.Button(self.time_label, label="重置")
        self.update_btn = wx.Button(self.time_label, label="更新")
        self.status_label = CenteredText(self, label="未知")
        self.player_online_overview = PlayerOnlineOverviewPanel(self)
        self.card_list = PlayerCardList(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self.reset_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        btn_sizer.Add(self.update_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        self.time_label.SetSizer(btn_sizer)
        sizer.Add(self.time_label, 0, wx.EXPAND)
        sizer.Add(self.status_label, 0, wx.EXPAND)
        sizer.AddSpacer(5)
        sizer.Add(self.player_online_overview, 0, wx.EXPAND)
        sizer.AddSpacer(5)
        sizer.Add(self.card_list, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.time_label.SetFont(ft(24))
        self.status_label.SetFont(ft(24))
        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
        self.update_btn.Bind(wx.EVT_BUTTON, self.on_update)

    def on_reset(self, _):
        if len(self.data_manager.points) > 0:
            point: ServerPoint = list(self.data_manager.points)[-1]
            self.update_data([p.name for p in point.players], point.time, ServerStatus.ONLINE)

    def on_update(self, _):
        event = GetStatusNowEvent()
        event.SetEventObject(self)
        self.ProcessEvent(event)

    def add_players(self, players: list[str]):
        self.card_list.add_players(players)

    def update_data(self, players: list[str], timestamp: float, status: ServerStatus) -> None:
        self.Freeze()
        self.time_label.SetLabel("时间: " + strftime("%Y-%m-%d %H:%M:%S", localtime(timestamp)))
        if status == ServerStatus.ONLINE:
            self.status_label.SetLabel("在线")
            self.status_label.SetBackgroundColour(wx.Colour(128, 255, 128))
            self.card_list.update_players(players)
        elif status == ServerStatus.UNKNOWN:
            self.status_label.SetLabel("未知")
            self.status_label.SetBackgroundColour(wx.Colour(128, 128, 128))
            self.card_list.update_players([])
        else:
            self.status_label.SetLabel("离线")
            self.status_label.SetBackgroundColour(wx.Colour(128, 128, 128))
        self.Thaw()
        self.Layout()
