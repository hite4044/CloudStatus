"""
配置面板
提供 GUI化配置编辑 的GUI定义文件
"""
from copy import copy
from dataclasses import dataclass
from typing import Any

from winsound import Beep

from gui.events import ApplyValueEvent, EVT_APPLY_VALUE
from gui.widget import *
from lib.config import config
from lib.data import MAX_SIZE


@dataclass
class LineData:
    label: str
    config_key: str
    fmt: type[Any]
    tip: str | None = None
    range: tuple[int | float, int | float] | None = None


class EntrySlider(wx.Panel):
    def __init__(self,
                 parent: wx.Window,
                 value: int | float,
                 area: tuple[int, int] = None,
                 step: int = 1,
                 ):
        super().__init__(parent)
        self.area = copy(area)
        self.fmt: type[int | float] = type(value)
        if area is None:
            area = (0, 100)
        self.value = value
        self.last_value = value

        self.slider = wx.Slider(self, value=int(value), minValue=area[0], maxValue=area[1], style=wx.SL_HORIZONTAL)
        self.slider.SetLineSize(step)
        self.entry = wx.TextCtrl(self, value=str(value), style=wx.TE_PROCESS_ENTER)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.slider, 1, wx.EXPAND)
        sizer.Add(self.entry, 0, wx.EXPAND)
        self.SetSizer(sizer)

        self.slider.Bind(wx.EVT_SLIDER, self.on_slider_change)
        self.slider.Bind(wx.EVT_LEFT_UP, self.on_slider_finalize)
        self.entry.Bind(wx.EVT_SET_FOCUS, self.on_start_edit)
        self.entry.Bind(wx.EVT_TEXT_ENTER, self.on_text_finalize)
        self.entry.Bind(wx.EVT_KILL_FOCUS, self.on_text_finalize)

    def on_slider_change(self, event: wx.Event):
        event.Skip()
        self.value = self.fmt(self.slider.GetValue())
        self.entry.SetValue(str(self.value))

    def on_slider_finalize(self, event: wx.Event):
        self.on_slider_change(event)
        self.update_value()

    def on_start_edit(self, event: wx.Event):
        event.Skip()
        self.last_value = self.fmt(self.entry.GetValue())

    def on_text_finalize(self, event: wx.Event):
        event.Skip()
        try:
            self.value = self.fmt(self.entry.GetValue())
            self.slider.SetValue(self.value)
            self.entry.SetValue(str(self.value))
            self.update_value()
        except ValueError as e:
            self.entry.SetValue(str(self.last_value))
            wx.MessageBox(str(e), "配置值不合法", wx.OK | wx.ICON_ERROR)

    def update_value(self):
        event = ApplyValueEvent()
        event.SetEventObject(self)
        self.ProcessEvent(event)

    def GetValue(self):
        return self.value


class IntEntrySlider(EntrySlider):
    def __init__(self,
                 parent: wx.Window,
                 value: int,
                 area: tuple[int, int] = None,
                 step: int = 1,
                 ):
        super().__init__(parent, value, area, step)
        self.fmt = int


class FloatEntrySlider(EntrySlider):
    def __init__(self,
                 parent: wx.Window,
                 value: float,
                 area: tuple[int, int] = None,
                 step: int = 1,
                 ):
        super().__init__(parent, value, area, step)
        self.fmt = float


class ConfigLine(wx.Panel):
    """用作配置修改"""

    def __init__(self, parent: wx.Window, data: LineData, use_sizer: bool = True,
                 cbk: Callable[[str, Any], None] = None):
        if use_sizer:
            super().__init__(parent)
            parent = self

        self.value = getattr(config, data.config_key)
        self.fmt = data.fmt
        self.key = data.config_key
        self.cbk = cbk
        self.last_value = str(self.value)

        self.label = CenteredText(parent, label=data.label, x_center=False)
        if self.fmt == str:
            self.widget = wx.TextCtrl(parent, value=self.value, style=wx.TE_PROCESS_ENTER)
        elif self.fmt == int:
            self.widget = IntEntrySlider(parent, self.value, area=data.range)
        elif self.fmt == float:
            self.widget = FloatEntrySlider(parent, self.value, area=data.range)
        elif self.fmt == bool:
            self.widget = wx.CheckBox(parent)
            self.widget.SetValue(self.value)
        else:
            raise ValueError(f"Unsupported fmt: {self.fmt}")
        self.widget.SetMaxSize((MAX_SIZE[0], 28))
        self.widget.SetMinSize((MAX_SIZE[0], 28))
        if data.tip:
            self.label.SetToolTip(wx.ToolTip(data.tip))

        if use_sizer:
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(self.label, proportion=0)
            sizer.Add(self.widget, flag=wx.EXPAND, proportion=1)
            self.SetSizer(sizer)
            self.SetMaxSize((-1, 28))

        if self.fmt == bool:
            self.widget.Bind(wx.EVT_CHECKBOX, self.apply_value)
        elif self.fmt == str:
            self.widget.Bind(wx.EVT_KILL_FOCUS, self.apply_value)
            self.widget.Bind(wx.EVT_TEXT_ENTER, self.apply_value)
        else:
            self.widget.Bind(EVT_APPLY_VALUE, self.apply_value)

    def apply_value(self, event: wx.Event):
        self.cbk(self.key, self.get_value())
        if isinstance(event, wx.FocusEvent):
            event.Skip()

    def get_value(self) -> Any:
        return self.fmt(self.widget.GetValue())


class ConfigPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.config_map: list[LineData] = [
            LineData("服务器地址", "addr", str, "要监测的服务器的地址"),
            LineData("检查间隔", "check_inv", float, "两次检查之间的间隔 (秒)", (5, 600)),
            LineData("点/文件", "points_per_file", int, "每个文件存储的最大数据点数量", (100, 5000)),
            LineData("点/保存", "saved_per_points", int, "获取多少个数据点后保存一次数据", (1, 20)),
            LineData("最小在线时间", "min_online_time", int,
                     "数据分析时使用的单次最小在线时间\n小于该时间忽略此次在线 (秒)", (0, 600)),
            LineData("数据空隙修复间隔", "fix_sep", float, "数据点之间的空隙小于该值时 (秒), 通过增加假数据点自动修复", (100, 600)),
            LineData("数据文件夹", "data_dir", str, "存放路径点数据文件的文件夹"),
            LineData("数据加载线程数", "data_load_threads", int, "一般越大越快, 推荐 4-8", (1, 32)),
            LineData("启用保存数据功能", "enable_data_save", bool, "一般用于远程路径查看数据"),
            LineData("服务器名", "server_name", str, "重启程序生效"),
            LineData("使用LittleSkin", "use_little_skin", bool,
                     "是否使用LittleSkin站加载皮肤, 否则使用正版皮肤\n注：需要清除头像缓存文件夹"),
        ]
        sizer = wx.FlexGridSizer(len(self.config_map) + 1, 2, 5, 5)
        self.SetFont(ft(11))
        for data in self.config_map:
            line = ConfigLine(self, data, use_sizer=False, cbk=config.set_value)
            sizer.Add(line.label, proportion=0, flag=wx.EXPAND)
            sizer.Add(line.widget, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)
