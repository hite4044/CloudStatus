"""
widget.py
在此项目中用到的:
实用小部件&实用函数
"""
import wx
from enum import Enum
from datetime import datetime, time as dt_time, date as dt_date, timedelta
from time import perf_counter
from wx.adv import DatePickerCtrl


font_cache: dict[int, wx.Font] = {}
maxsize = 1919810
GA_LOOP_TIME = 5
GA_WAIT_TIME = 2


def ft(size: int):
    if size not in font_cache:
        font_cache[size] = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font_cache[size].SetPointSize(size)
    return font_cache[size]


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


class FormatedText(wx.StaticText):
    def __init__(self, parent: wx.Window, fmt: str):
        super().__init__(parent, label=fmt)
        self.fmt = fmt

    def format(self, *texts):
        self.SetLabel(self.fmt.format(*texts))


class BarMode(Enum):
    DETERMINATE = 0
    INDETERMINATE = 1


class BarColor:
    BACKGROUND = (230, 230, 230)
    BAR = (6, 176, 37)
    BORDER = (188, 188, 188)


# noinspection PyPep8Naming
class CustomProgressBar(wx.Control):
    def __init__(self, parent, id_=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize, max_value=100,
                 style=wx.NO_BORDER):
        super(CustomProgressBar, self).__init__(parent, id_, pos, size, style, wx.DefaultValidator, "CustomProgressBar")

        self.value = 0
        self.max_value = max_value
        self.mode: BarMode = BarMode.INDETERMINATE

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def SetValue(self, value):
        if 0 <= value <= self.max_value:
            self.value = value
            self.mode = BarMode.DETERMINATE
            self.Refresh()
        else:
            raise ValueError(f"Value must be between 0 and {self.max_value}")

    def Pulse(self):
        self.mode = BarMode.INDETERMINATE
        self.Refresh()

    def OnPaint(self, _):
        dc = wx.PaintDC(self)
        width, height = self.GetClientSize()
        width -= 2
        height -= 2

        dc.SetBrush(wx.Brush(BarColor.BACKGROUND))
        dc.DrawRectangle(-1, -1, width + 4, height + 4)
        dc.Clear()
        dc.SetPen(wx.Pen(BarColor.BAR))
        dc.SetBrush(wx.Brush(BarColor.BAR))  # 因为不知道怎么不画出边框，所以用同样的颜色掩盖一下
        if self.mode == BarMode.DETERMINATE:
            progress_width = int((self.value / self.max_value) * width)
            dc.DrawRectangle(1, 1, progress_width - 1, height)
        else:
            loop_time = (perf_counter() % GA_LOOP_TIME + GA_WAIT_TIME)
            pulse_width = int(width * 0.1)
            if loop_time < GA_LOOP_TIME:
                pulse_start = (width + pulse_width) * (loop_time / GA_LOOP_TIME) - pulse_width  # 计算滑块的起始位置
                dc.DrawRectangle(int(pulse_start), 1, pulse_width - 1, height)
        dc.SetPen(wx.Pen(BarColor.BORDER))
        dc.DrawLines([(0, 0), (width + 1, 0), (width + 1, height + 1), (0, height + 1), (0, 0)])

    def OnSize(self, event):
        self.Refresh()
        event.Skip()


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
