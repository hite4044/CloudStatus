"""
预览面板
提供 服务器预览 的GUI定义文件
"""
from enum import Enum
from threading import Thread
from time import strftime, localtime, time

import wx
from PIL import Image

from gui.events import GetStatusNowEvent
from gui.widget import ft, CenteredText, CenteredBitmap, GradientBgBinder, load_player_head, EasyColor, PlayerOnlineWin
from lib.common_data import common_data
from lib.data import ServerPoint
from lib.log import logger

MAX_HAP = 20
MIN_HAP = 6


class ServerStatus(Enum):
    ONLINE = 0
    OFFLINE = 1


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
        self.head = PlayerHead(self)
        self.name_label = NameLabel(self, label=name, size=(-1, 32))
        Thread(target=load_player_head, args=(name, self.load_head, 80)).start()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.head, flag=wx.EXPAND, proportion=1)
        sizer.Add(self.name_label, flag=wx.EXPAND, proportion=0)
        self.SetSizer(sizer)
        self.head.Bind(wx.EVT_RIGHT_UP, self.on_menu_click)

    def on_menu_click(self, _):
        menu = wx.Menu()
        menu.Append(wx.ID_COPY, "复制名字")
        menu.Append(wx.ID_REFRESH, "刷新头像")
        menu.Bind(wx.EVT_MENU, lambda _: wx.TheClipboard.SetData(wx.TextDataObject(self.player)), id=wx.ID_COPY)
        menu.Bind(wx.EVT_MENU, self.refresh_head, id=wx.ID_REFRESH)
        self.PopupMenu(menu)
        menu.Destroy()

    def refresh_head(self, *_):
        logger.info("刷新头像")
        Thread(target=load_player_head, args=(self.player, self.load_head, 80, True)).start()

    def load_card_color(self):
        """从玩家头像中提取两个眼睛的颜色并应用到控件中"""
        image = Image.open(f"heads_cache/{self.player}_80.png")
        left_eye = image.getpixel((28, 58))[:3]
        right_eye = image.getpixel((58, 58))[:3]

        if left_eye == right_eye:
            color_left = color_right = EasyColor(*right_eye)
        else:
            color_left, color_right = EasyColor(*left_eye), EasyColor(*right_eye)
        self.head.set_color(color_left.set_luminance(0.5).wxcolor, color_right.set_luminance(0.7).wxcolor)
        self.name_label.set_color(color_left.set_luminance(0.9).wxcolor, color_right.set_luminance(0.8).wxcolor)
        self.Refresh()

    def load_head(self, head: wx.Bitmap):
        if not self:
            return
        self.head.SetBitmap(head)
        self.load_card_color()
        self.Layout()


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
        self.SetVirtualSize(1316, 630)
        self.SetScrollRate(0, 20)

    def on_card_open(self, event: wx.MouseEvent):
        """当双击玩家卡片"""
        card: PlayerCard = event.GetEventObject().GetParent()
        if card.player in self.cards:
            PlayerOnlineWin(self, card.player).Show()

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
        self.Layout()
        self.Refresh()

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
        elif now_cols != self.old_cols:
            self.sizer.SetCols(now_cols)
            self.sizer.Layout()
            self.old_cols = now_cols


class OverviewPanel(wx.Panel):
    """预览面板, 相当于地基"""

    def __init__(self, parent: wx.Window):
        wx.Panel.__init__(self, parent)
        self.data_manager = common_data.data_manager
        self.time_label = CenteredText(self, label="时间: 2025-02-14 21:51:39")
        self.reset_btn = wx.Button(self.time_label, label="重置")
        self.update_btn = wx.Button(self.time_label, label="更新")
        self.status_label = CenteredText(self, label="未知")
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
        sizer.Add(self.card_list, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.time_label.SetFont(ft(24))
        self.status_label.SetFont(ft(24))
        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
        self.update_btn.Bind(wx.EVT_BUTTON, self.on_update)
        # noinspection SpellCheckingInspection
        self.update_data(["hite404", "lwuxianfengguang", "Olaire", "Cherries_", "haijinzi", "water_melon_awa"], time(),
                         ServerStatus.ONLINE)

    def on_reset(self, _):
        point: ServerPoint = list(self.data_manager.points)[-1]
        self.update_data([p.name for p in point.players], point.time, ServerStatus.ONLINE)

    def on_update(self, _):
        event = GetStatusNowEvent()
        event.SetEventObject(self)
        self.ProcessEvent(event)

    def update_data(self, players: list[str], timestamp: float, status: ServerStatus) -> None:
        self.Freeze()
        self.time_label.SetLabel("时间: " + strftime("%Y-%m-%d %H:%M:%S", localtime(timestamp)))
        if status == ServerStatus.ONLINE:
            self.status_label.SetLabel("在线")
            self.status_label.SetBackgroundColour(wx.Colour(128, 255, 128))
            self.card_list.update_players(players)
        else:
            self.status_label.SetLabel("离线")
            self.status_label.SetBackgroundColour(wx.Colour(128, 128, 128))
        self.Thaw()
        self.Layout()
