from enum import Enum
from os import mkdir
from os.path import isdir, isfile
from threading import Thread
from time import strftime, localtime, time
from typing import Callable

import wx
from PIL import Image
from colour import Color

from gui.events import GetStatusNowEvent
from gui.widget import ft, CenteredStaticText, CenteredBitmap, get_gradient_bitmap, GradientDirection
from lib.data import ServerPoint
from lib.log import logger
from lib.skin import request_player_skin, render_player_head

MAX_HAP = 20
MIN_HAP = 6


class ServerStatus(Enum):
    ONLINE = 0
    OFFLINE = 1


def load_player_head(name: str, cbk: Callable[[wx.Bitmap], None], target_size: int = 64, no_cache: bool = False):
    if not isdir("heads_cache"):
        mkdir("heads_cache")

    if not isfile(f"heads_cache/{name}_{target_size}.png") or no_cache:
        skin = request_player_skin(name)
        head = render_player_head(skin, target_size)
        head.save(f"heads_cache/{name}_{target_size}.png")
    cbk(wx.Bitmap(f"heads_cache/{name}_{target_size}.png"))


class EasyColor:
    def __init__(self, red: int, green: int, blue: int):
        self.color = Color()
        self.color.set_rgb((red / 255, green / 255, blue / 255))

    def set_luminance(self, luminance: float):
        self.color.set_luminance(luminance)

    def get_rgb(self):
        return [int(255 * c) for c in self.color.rgb]


class NameLabel(CenteredStaticText):
    def __init__(self, parent: wx.Window, label: str, size=wx.DefaultSize):
        super().__init__(parent, label=label, size=size)
        self.color1 = self.GetBackgroundColour()
        self.color2 = self.GetBackgroundColour()
        self.bmp = get_gradient_bitmap(self.color1, self.color2, self.Size, GradientDirection.HORIZONTAL)
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def set_color(self, color: wx.Colour, color2: wx.Colour = wx.NullColour):
        self.color1 = wx.Colour(color)
        if not color2.IsOk():
            self.color2 = wx.Colour(self.color1)
        self.bmp = get_gradient_bitmap(self.color1, self.color2, self.Size, GradientDirection.HORIZONTAL)

    def on_paint(self, _):
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self.bmp, (0, 0))
        super().on_paint(None)


class PlayerCard(wx.Panel):
    def __init__(self, parent: wx.Window, name: str):
        wx.Panel.__init__(self, parent, size=(180, 180))
        self.player = name
        self.color1 = self.GetBackgroundColour()
        self.color2 = self.GetBackgroundColour()
        self.bmp = get_gradient_bitmap(self.color1, self.color2, self.Size, GradientDirection.HORIZONTAL)
        self.head = CenteredBitmap(self)
        self.name_label = NameLabel(self, label=name, size=(-1, 32))
        Thread(target=load_player_head, args=(name, self.load_head, 80)).start()
        self.set_best_font_size()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.head, flag=wx.EXPAND, proportion=1)
        sizer.Add(self.name_label, flag=wx.EXPAND, proportion=0)
        self.SetSizer(sizer)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.head.Bind(wx.EVT_RIGHT_UP, self.on_menu_click)

    def on_size(self, event: wx.SizeEvent):
        event.Skip()
        self.Refresh()

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

    def set_best_font_size(self):
        dc = wx.ClientDC(self)
        ft_size = 18
        while True:
            dc.SetFont(ft(ft_size))
            size = dc.GetTextExtent(self.name_label.GetLabel())
            if size[0] > 180:
                ft_size -= 1
            else:
                break
        self.name_label.SetFont(ft(ft_size))

    def load_card_color(self):
        image = Image.open(f"heads_cache/{self.player}_80.png")
        left_eye = image.getpixel((28, 58))[:3]
        right_eye = image.getpixel((58, 58))[:3]

        if left_eye == right_eye:
            color = EasyColor(*right_eye)
            color.set_luminance(0.6)
            self.color1 = self.color2 = wx.Colour(color.get_rgb())
            self.head.set_color(wx.Colour(color.get_rgb()))
            color.set_luminance(0.8)
            self.name_label.set_color(wx.Colour(color.get_rgb()))
        else:
            print(self.player)
            color_left, color_right = EasyColor(*left_eye), EasyColor(*right_eye)
            color_left.set_luminance(0.6)
            color_right.set_luminance(0.6)
            self.color1 = wx.Colour(color_left.get_rgb())
            self.color2 = wx.Colour(color_right.get_rgb())
            self.head.set_color(wx.Colour(color_left.get_rgb()), wx.Colour(color_right.get_rgb()))
            color_left, color_right = EasyColor(*left_eye), EasyColor(*right_eye)
            color_left.set_luminance(0.8)
            color_right.set_luminance(0.8)
            self.name_label.set_color(wx.Colour(color_left.get_rgb()), wx.Colour(color_right.get_rgb()))
        self.bmp = get_gradient_bitmap(self.color1, self.color2, self.Size, GradientDirection.HORIZONTAL)
        self.Refresh()

    def on_paint(self, _):
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self.bmp, (0, 0))

    def load_head(self, head: wx.Bitmap):
        self.head.SetBitmap(head)
        self.load_card_color()
        self.Layout()


class PlayerCardList(wx.ScrolledWindow):
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

    def update_players(self, players: list[str]) -> None:
        for card in self.cards.values():
            self.sizer.Detach(card)
            card.Destroy()
        self.cards.clear()
        for player in players:
            card = PlayerCard(self, player)
            self.cards[player] = card
            self.sizer.Add(card, flag=wx.EXPAND)
        self.on_size(None)
        self.Layout()
        self.Refresh()

    def on_size(self, _):
        width = self.GetSize()[0]
        self.SetVirtualSize(width, (len(self.cards) // self.old_cols + 1) * (
                180 + self.sizer.GetHGap()) - self.sizer.GetHGap())
        now_cols = int(width / 185)
        if now_cols > 1:
            now_hgap = max(MIN_HAP, min(MAX_HAP, (self.GetSize()[0] - (now_cols * 180)) // (now_cols - 1)))
        else:
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
    def __init__(self, parent: wx.Window):
        wx.Panel.__init__(self, parent)
        self.time_label = CenteredStaticText(self, label="时间: 2025-02-14 21:51:39")
        self.reset_btn = wx.Button(self.time_label, label="重置")
        self.update_btn = wx.Button(self.time_label, label="更新")
        self.status_label = CenteredStaticText(self, label="未知")
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
        self.update_data(["hite404", "lwuxianfengguang", "Olaire", "Cherries_", "haijinzi", "water_melon_awa"], time(),
                         ServerStatus.ONLINE)

    def on_reset(self, _):
        point: ServerPoint = list(the_data_manager.points)[-1]
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
