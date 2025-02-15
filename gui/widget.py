"""
widget.py
在此项目中用到的:
实用小部件&实用函数
"""
from datetime import datetime, time as dt_time, date as dt_date, timedelta
from enum import Enum

import wx
from PIL import ImageDraw
from PIL import Image
from wx.adv import DatePickerCtrl

font_cache: dict[int, wx.Font] = {}
maxsize = 1919810
GA_LOOP_TIME = 5
GA_WAIT_TIME = 2


class GradientDirection(Enum):
    HORIZONTAL = 0
    VERTICAL = 1


def ft(size: int):
    if size not in font_cache:
        font_cache[size] = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font_cache[size].SetPointSize(size)
    return font_cache[size]


def get_gradient_bitmap(color1: wx.Colour, color2: wx.Colour, size: tuple[int, int], dir_: GradientDirection):
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
    return bitmap.ConvertToBitmap()


class CenteredStaticText(wx.StaticText):
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
        super().__init__(parent, id_, bitmap, pos, size, style, name)
        self.x_center = x_center
        self.y_center = y_center
        self.color1 = self.color2 = self.GetBackgroundColour()
        self.background = get_gradient_bitmap(self.color1, self.color2, self.Size, GradientDirection.HORIZONTAL)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)

    def on_size(self, event: wx.SizeEvent):
        event.Skip()
        self.background = get_gradient_bitmap(self.color1, self.color2, self.Size, GradientDirection.HORIZONTAL)

    def set_color(self, color: wx.Colour, color2: wx.Colour = wx.NullColour):
        self.color1 = wx.Colour(color)
        if color2.IsOk():
            self.color2 = wx.Colour(color2)
        else:
            self.color2 = wx.Colour(color)
        self.background = get_gradient_bitmap(self.color1, self.color2, self.Size, GradientDirection.HORIZONTAL)
        self.Refresh()

    def on_paint(self, _):
        try:
            dc = wx.PaintDC(self)
        except RuntimeError:
            return
        bitmap: wx.Bitmap = self.GetBitmap()
        dc.DrawBitmap(self.background, (0, 0))
        if bitmap.IsOk():
            size = self.GetSize()
            dc.DrawBitmap(bitmap, ((size[0] - bitmap.GetWidth()) // 2) * int(self.x_center),
                          ((size[1] - bitmap.GetHeight()) // 2) * int(self.y_center))


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


class ToolTip(wx.Frame):
    def __init__(self, parent: wx.Window, text: str):
        super().__init__(parent, style=wx.FRAME_TOOL_WINDOW | wx.FRAME_FLOAT_ON_PARENT | wx.NO_BORDER)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self.SetFont(parent.GetFont())
        self.parent = parent
        self.label = wx.StaticText(self, label=text)
        parent.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.label.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.label.SetDoubleBuffered(True)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.check_visible)
        self.timer.Start(300)

    def check_visible(self, _):
        screen_mouse = wx.GetMousePosition()
        if not self.parent.GetScreenRect().Contains(*screen_mouse):
            self.Hide()

    def on_mouse_move(self, event: wx.MouseEvent):
        mouse = wx.GetMousePosition()
        if event.GetEventObject() == self.label:
            local_pos = mouse[0] - self.parent.ScreenPosition[0], mouse[1] - self.parent.ScreenPosition[1]
            event.SetPosition(wx.Point(*local_pos))
            event.SetEventObject(self.parent)
            self.parent.ProcessEvent(event)
        self.SetPosition((mouse[0], mouse[1] - self.GetSize()[1]))
        event.Skip()

    def set_tip(self, tip: str = None):
        if tip is None:
            self.Hide()
            return
        else:
            self.Show()
        self.Freeze()
        self.label.SetLabel(tip)
        dc = wx.ClientDC(self)
        dc.SetFont(self.parent.GetFont())
        w, h = dc.GetMultiLineTextExtent(tip)
        w += 3
        self.SetSize(wx.Size(w, h))
        self.label.SetSize(self.GetSize())
        self.Thaw()
