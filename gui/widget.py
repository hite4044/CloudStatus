"""
widget.py
在此项目中用到的:
实用小部件&实用函数
"""
from dataclasses import dataclass
from datetime import datetime, time as dt_time, date as dt_date, timedelta
from enum import Enum
from os import mkdir
from os.path import isfile, isdir
from typing import Callable

import wx
from PIL import Image
from PIL import ImageDraw
from colour import Color
from wx.adv import DatePickerCtrl

from lib.config import config
from lib.skin_loader import request_player_skin, render_player_head, SkinLoadWay

font_cache: dict[int, wx.Font] = {}
maxsize = 1919810
GA_LOOP_TIME = 5
GA_WAIT_TIME = 2


class GradientDirection(Enum):
    HORIZONTAL = 0
    VERTICAL = 1


class ProgressStatus(Enum):
    WAIT = 0
    STATUS = 1
    FP_STATUS = 2
    FP_WAIT = 3
    PAUSE = 4


@dataclass
class StatusStatus:
    status: ProgressStatus
    times: int = 0
    players_left: int = 0


def ft(size: int):
    if size not in font_cache:
        font_cache[size] = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font_cache[size].SetPointSize(size)
    return font_cache[size]


def tuple_fmt_time(seconds: float) -> tuple[int, int, int, int]:
    """转化时间戳至时间元组"""
    return int(seconds // 3600 // 24), int(seconds // 3600 % 24), int(seconds % 3600 // 60), int(seconds % 60)


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


def load_player_head(name: str, cbk: Callable[[wx.Bitmap], None], target_size: int = 64, no_cache: bool = False):
    """
    加载玩家头像至Bitmap
    :param name: 玩家名称
    :param cbk: 加载回调函数
    :param target_size: 目标渲染大小
    :param no_cache: 不使用缓存
    """
    if not isdir("heads_cache"):
        mkdir("heads_cache")

    if not isfile(f"heads_cache/{name}_{target_size}.png") or no_cache:
        skin = request_player_skin(name, SkinLoadWay.LITTLE_SKIN if config.use_little_skin else SkinLoadWay.MOJANG)
        if skin is None:
            head = Image.open("assets/default_skin/error_head.png")
        else:
            head = render_player_head(skin, target_size)
        head = head.convert("RGBA")
        head.save(f"heads_cache/{name}_{target_size}.png")
    bitmap = wx.Image()
    bitmap.LoadFile(f"heads_cache/{name}_{target_size}.png")
    wx.CallAfter(cbk, bitmap)


class EasyColor:
    """原版的color对象一坨, 自己封装一个"""

    def __init__(self, red: int, green: int, blue: int):
        self.color = Color()
        self.color.set_rgb((red / 255, green / 255, blue / 255))

    def set_luminance(self, luminance: float):
        self.color.set_luminance(luminance)
        return self

    @property
    def wxcolor(self) -> wx.Colour:
        return wx.Colour(self.get_rgb())

    @property
    def rgb(self) -> list[int]:
        return [int(255 * c) for c in self.color.rgb]

    def get_rgb(self):
        return self.rgb

    def get_wxcolor(self) -> wx.Colour:
        return self.wxcolor


class GradientBgBinder:
    def __init__(self, window: wx.Window, dir_: GradientDirection = GradientDirection.HORIZONTAL):
        self.bg_bitmap: wx.Bitmap = wx.NullBitmap
        self.color1: wx.Colour = wx.NullColour
        self.color2: wx.Colour = wx.NullColour
        self.win: wx.Window = window
        self.direction = dir_
        self.refresh_bg_call = wx.CallLater(0, self.refresh_bg)
        window.Bind(wx.EVT_PAINT, self.on_paint)
        window.Bind(wx.EVT_SIZE, self.on_size)
        window.Bind(wx.EVT_WINDOW_DESTROY, self.on_destroy)
        window.SetBackgroundStyle(wx.BG_STYLE_PAINT)

    def set_color(self, color1: wx.Colour, color2: wx.Colour = wx.NullColour):
        self.color1 = wx.Colour(color1)
        if color2.IsOk():
            self.color2 = wx.Colour(color2)
        else:
            self.color2 = wx.Colour(color1)
        self.refresh_bg()

    def refresh_bg(self):
        self.refresh_bg_call.Stop()
        bitmap = get_gradient_bitmap(self.color1, self.color2, self.win.Size, self.direction)
        if bitmap is None:
            return
        self.bg_bitmap = bitmap
        self.win.Refresh()

    def on_size(self, event: wx.SizeEvent):
        if not self.refresh_bg_call.IsRunning():
            self.refresh_bg_call.Start(100)
        event.Skip()

    def on_paint(self, event: wx.PaintEvent):
        if self.win is None:
            return
        dc = wx.PaintDC(self.win)
        if self.bg_bitmap.IsOk():
            dc.DrawBitmap(self.bg_bitmap, (0, 0))
        event.Skip()

    def on_destroy(self, _):
        self.refresh_bg_call.Stop()
        self.win = None
        self.bg_bitmap = None
        self.color1 = None
        self.color2 = None
        del self


def get_gradient_bitmap(color1: wx.Colour, color2: wx.Colour, size: tuple[int, int],
                        dir_: GradientDirection) -> wx.Bitmap | None:
    width, height = size
    if color1.GetRGB() == color2.GetRGB():
        image = Image.new("RGB", (width, height), color1.GetRGB())
    else:
        image = Image.new("RGB", (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(image)
        if dir_ == GradientDirection.HORIZONTAL:
            for x in range(width):
                r = int(color1[0] + (color2[0] - color1[0]) * x / width)
                g = int(color1[1] + (color2[1] - color1[1]) * x / width)
                b = int(color1[2] + (color2[2] - color1[2]) * x / width)
                draw.line((x, 0, x, height), fill=(r, g, b))
        elif dir_ == GradientDirection.VERTICAL:
            for y in range(height):
                r = int(color1[0] + (color2[0] - color1[0]) * y / height)
                g = int(color1[1] + (color2[1] - color1[1]) * y / height)
                b = int(color1[2] + (color2[2] - color1[2]) * y / height)
                draw.line((0, y, width, y), fill=(r, g, b))
        else:
            raise ValueError("Invalid direction")
    bitmap = wx.Image(image.width, image.height, image.tobytes())
    if not bitmap.IsOk():
        return None
    return bitmap.ConvertToBitmap()


class NoTabNotebook(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent, style=wx.TRANSPARENT_WINDOW)
        self.panels: list[wx.Window] = []
        self.now_window: wx.Window | None = None
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)

    def add_page(self, window: wx.Window):
        self.panels.append(window)
        window.Hide()
        if not self.now_window:
            self.now_window = window
            self.sizer.Add(window, 1, wx.EXPAND)
            self.Layout()

    def switch_page(self, index: int):
        if self.now_window:
            self.now_window.Hide()
        self.now_window = self.panels[index]
        self.panels[index].Show()
        self.sizer.Clear()
        self.sizer.Add(self.panels[index], 1, wx.EXPAND)
        self.Layout()
        self.Refresh()
        self.now_window.Refresh()


class CenteredText(wx.StaticText):
    """使得绘制的文字始终保持在控件中央"""

    def __init__(
            self,
            parent,
            id_=wx.ID_ANY,
            label=wx.EmptyString,
            pos=wx.DefaultPosition,
            size=wx.DefaultSize,
            style=0,
            name=wx.StaticTextNameStr,
            x_center=True,
            y_center=True,
    ):
        super().__init__(parent, id_, label, pos, size, style, name)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.x_center = x_center
        self.y_center = y_center

    def on_paint(self, _):
        dc = wx.PaintDC(self)
        label = self.GetLabel()
        dc.SetFont(self.GetFont())
        text_size = dc.GetTextExtent(label)
        size = self.GetSize()

        dc.DrawText(
            label,
            ((size[0] - text_size[0]) // 2) * int(self.x_center),
            ((size[1] - text_size[1]) // 2) * int(self.y_center),
        )


class TransparentCenteredText(CenteredText):
    def __init__(
            self,
            parent,
            id_=wx.ID_ANY,
            label=wx.EmptyString,
            pos=wx.DefaultPosition,
            size=wx.DefaultSize,
            style=0,
            name=wx.StaticTextNameStr,
            x_center=True,
            y_center=True,
    ):
        super().__init__(parent, id_, label, pos, size, style | wx.TRANSPARENT_WINDOW, name)
        self.x_center = x_center
        self.y_center = y_center
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)


class CenteredBitmap(wx.StaticBitmap):
    def __init__(
            self,
            parent,
            id_=wx.ID_ANY,
            bitmap=wx.NullBitmap,
            pos=wx.DefaultPosition,
            size=wx.DefaultSize,
            style=0,
            name=wx.StaticBitmapNameStr,
            x_center=True,
            y_center=True,
    ):
        super().__init__(parent, id_, bitmap, pos, size, style | wx.TRANSPARENT_WINDOW, name)
        self.x_center = x_center
        self.y_center = y_center
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)

    def on_paint(self, _):
        try:
            bdc = wx.PaintDC(self)
        except RuntimeError:
            return
        dc = wx.GCDC(bdc)
        bitmap: wx.Bitmap = self.GetBitmap()
        if bitmap.IsOk():
            size = self.GetSize()
            dc.DrawBitmap(bitmap, ((size[0] - bitmap.GetWidth()) // 2) * int(self.x_center),
                          ((size[1] - bitmap.GetHeight()) // 2) * int(self.y_center), True)


class FormatedText(wx.StaticText):
    def __init__(self, parent: wx.Window, fmt: str):
        super().__init__(parent, label=fmt)
        self.fmt = fmt

    def format(self, *texts):
        self.SetLabel(self.fmt.format(*texts))


class TimeSelector(wx.Panel):
    def __init__(self, parent: wx.Window, height: int = 29):
        super().__init__(parent)
        self.hour_enable = False

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        label = CenteredText(self, label="日期: ")
        label.SetMinSize((-1, height))
        self.date_ctrl = DatePickerCtrl(self, size=(115, height))
        self.enable_hour_check = wx.CheckBox(self)
        self.enable_hour_check.SetMinSize((-1, height))
        self.label_hour = CenteredText(self, label="时: ")
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


class ToolTip(wx.Frame):
    def __init__(self, parent: wx.Window, text: str):
        super().__init__(parent, style=wx.FRAME_TOOL_WINDOW | wx.BORDER | wx.TRANSPARENT_WINDOW)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self.SetFont(parent.GetFont())
        self.parent = parent
        self.label = wx.StaticText(self, label=text, pos=(10, 0))
        parent.Bind(wx.EVT_WINDOW_DESTROY, self.on_parent_destroy)
        parent.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.label.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.label.SetDoubleBuffered(True)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.check_visible)
        self.timer.Start(100)

    def check_visible(self, _):
        screen_mouse = wx.GetMousePosition()
        if not self.parent.GetScreenRect().Contains(*screen_mouse):
            self.Hide()

    def on_mouse_move(self, event: wx.MouseEvent):
        mouse = wx.GetMousePosition()
        if event.GetEventObject() != self.parent:
            local_pos = mouse[0] - self.parent.ScreenPosition[0], mouse[1] - self.parent.ScreenPosition[1]
            event.SetPosition(wx.Point(*local_pos))
            event.SetEventObject(self.parent)
            self.parent.ProcessEvent(event)
        self.SetPosition((mouse[0], mouse[1] - self.GetSize()[1] - 5))
        event.Skip()

    def set_tip(self, tip: str = None):
        if not tip:
            self.Hide()
            return
        else:
            self.Show()
        self.Freeze()
        self.label.SetLabel(tip)
        dc = wx.ClientDC(self)
        dc.SetFont(self.parent.GetFont())
        w, h = dc.GetMultiLineTextExtent(tip)
        w += 10
        h += 4
        self.SetSize(wx.Size(w, h))
        self.label.SetPosition(wx.Point(3, 0))
        mouse = wx.GetMousePosition()
        self.SetPosition((mouse[0], mouse[1] - self.GetSize()[1] - 5))
        self.Thaw()

    def on_parent_destroy(self, _):
        self.timer.Stop()
        self.timer.Destroy()
        self.Destroy()


class LabeledData(wx.Panel):
    def __init__(self, parent: wx.Window, label: str, data: str):
        super().__init__(parent)
        self.SetWindowStyle(wx.SIMPLE_BORDER)
        self.label_t = wx.StaticText(self, label=label)
        self.data_t = wx.StaticText(self, label=data)
        self.label_t.SetForegroundColour(wx.Colour(152, 152, 152))
        self.label_t.SetFont(ft(12))
        self.data_t.SetFont(ft(20))
        v_sizer = wx.BoxSizer(wx.VERTICAL)
        v_sizer.AddSpacer(10)
        v_sizer.Add(self.label_t)
        v_sizer.Add(self.data_t)
        v_sizer.AddSpacer(10)
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_sizer.AddSpacer(10)
        h_sizer.Add(v_sizer)
        h_sizer.AddSpacer(10)
        self.SetSizer(h_sizer)

        self.label_t.Bind(wx.EVT_LEFT_DCLICK, lambda e: self.ProcessEvent(e))
        self.data_t.Bind(wx.EVT_LEFT_DCLICK, lambda e: self.ProcessEvent(e))

    def SetLabel(self, label):
        self.label_t.SetLabel(label)

    def SetData(self, data: str):
        self.data_t.SetLabel(data)


class DataShowDialog(wx.Dialog):
    def __init__(self, parent: wx.Window, data: list[str], header: str = "数据", title: str = "数据"):
        super().__init__(parent, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, size=(380, 400))
        self.SetFont(ft(11))
        self.SetTitle(title)
        self.data_lc = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.data_lc.InsertColumn(0, header, width=300)
        for i, d in enumerate(data):
            self.data_lc.InsertItem(i, d)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.data_lc, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)

        self.data_lc.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.menu)

    def get_selection(self) -> list[int]:
        first = self.data_lc.GetFirstSelected()
        if first == -1:
            return []
        result = []
        while first != -1:
            result.append(first)
            first = self.data_lc.GetNextSelected(first)
        return result

    def menu(self, event: wx.ListEvent):
        event.Skip()
        selection = self.get_selection()
        if not selection:
            return
        menu = wx.Menu()
        menu.Append(1, "复制数据")
        menu.Bind(wx.EVT_MENU, self.copy_selected, id=1)
        self.PopupMenu(menu)

    def copy_selected(self, _):
        selection = self.get_selection()
        if not selection:
            return
        data = [self.data_lc.GetItem(i, 0).GetText() for i in selection]
        clip: wx.Clipboard = wx.TheClipboard
        clip.Open()
        clip.SetData(wx.TextDataObject("\n".join(data)))
        clip.Close()
