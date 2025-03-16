"""
配置面板
提供 GUI化配置编辑 的GUI定义文件
"""
import os
from copy import copy
from dataclasses import dataclass
from typing import Any

from gui.events import ApplyValueEvent, EVT_APPLY_VALUE
from gui.widget import *
from lib.common_data import common_data
from lib.config import config, DataSaveFmt
from lib.data import MAX_SIZE


@dataclass
class LineData:
    label: str
    config_key: str
    fmt: type[Any]
    tip: str | None = None
    range: tuple[int | float, int | float] | None = None
    items_desc: dict[Enum, str] | None = None


class EntrySlider(wx.Panel):
    def __init__(self,
                 parent: wx.Window,
                 value: int | float,
                 area: tuple[float, float] = None,
                 step: int = 1,
                 ):
        super().__init__(parent)
        if area is None:
            area = (0, 100)
        self.area = copy(area)
        self.fmt: type[int | float] = type(value)
        self.value = value
        self.last_value = value
        self.mult = 1 if self.fmt == int else 10

        self.slider = wx.Slider(self, value=int(value * self.mult), style=wx.SL_HORIZONTAL,
                                minValue=int(area[0] * self.mult), maxValue=int(area[1] * self.mult))
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
        self.value = self.fmt(self.slider.GetValue() / self.mult)
        self.entry.SetValue(str(self.value))

    def on_slider_finalize(self, event: wx.Event):
        self.on_slider_change(event)
        self.update_value()

    def on_start_edit(self, event: wx.Event):
        event.Skip()
        self.last_value = self.fmt(self.entry.GetValue())

    def on_text_finalize(self, event: wx.Event):
        if event.GetClassName() != "wxCommandEvent":
            event.Skip()
        try:
            self.value = self.fmt(self.entry.GetValue())
            self.slider.SetValue(int(self.value * self.mult))
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
        elif isinstance(self.fmt, type(Enum)):
            self.widget = wx.Choice(parent, choices=[desc for _, desc in data.items_desc.items()])
            assert isinstance(self.value, Enum)
            self.widget.SetSelection(self.value.value)
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
        elif isinstance(self.fmt, type(Enum)):
            self.widget.Bind(wx.EVT_CHOICE, self.apply_value)
        else:
            self.widget.Bind(EVT_APPLY_VALUE, self.apply_value)

    def apply_value(self, event: wx.Event):
        self.cbk(self.key, self.get_value())
        if isinstance(event, wx.FocusEvent):
            event.Skip()

    def get_value(self) -> Any:
        if isinstance(self.widget, wx.Choice):
            return self.fmt(self.widget.GetSelection())
        else:
            # noinspection PyUnresolvedReferences
            return self.fmt(self.widget.GetValue())


class ConfigLinePanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.config_map: list[LineData] = [
            LineData("服务器地址", "addr", str, "要监测的服务器的地址"),
            LineData("检查间隔", "check_inv", float, "两次检查之间的间隔 (秒)", (5, 600)),
            LineData("点/文件", "points_per_file", int, "每个文件存储的最大数据点数量", (100, 5000)),
            LineData("点/保存", "saved_per_points", int, "获取多少个数据点后保存一次数据", (1, 20)),
            LineData("最小在线时间", "min_online_time", int,
                     "数据分析时使用的单次最小在线时间\n小于该时间忽略此次在线 (秒)", (0, 600)),
            LineData("数据空隙修复间隔", "fix_sep", float, "数据点之间的空隙小于该值时 (秒), 通过增加假数据点自动修复",
                     (100, 600)),
            LineData("数据文件夹", "data_dir", str, "存放路径点数据文件的文件夹"),
            LineData("数据加载线程数", "data_load_threads", int, "一般越大越快, 推荐 4-8", (1, 32)),
            LineData("启用保存数据功能", "enable_data_save", bool, "一般用于远程路径查看数据"),
            LineData("服务器名", "server_name", str, "重启程序生效"),
            LineData("使用LittleSkin", "use_little_skin", bool,
                     "是否使用LittleSkin站加载皮肤, 否则使用正版皮肤\n注：需要清除头像缓存文件夹"),
            LineData("数据文件格式", "data_save_fmt", DataSaveFmt,
                     tip="使用新的数据格式, 可以安全地随意切换数据格式 (保存性能可能不一样)\n保存数据时使用新的格式, 或者手动保存",
                     items_desc={
                         DataSaveFmt.NORMAL: "普通格式 (原数据)",
                         DataSaveFmt.PLAYER_MAPPING: "玩家映射格式 (更小)",
                     }),
            LineData("超时时间", "time_out", float, "获取服务器状态的超时时间 (秒)", (0.5, 6.0))
        ]
        sizer = wx.FlexGridSizer(len(self.config_map) + 1, 2, 5, 5)
        self.SetFont(ft(11))
        for data in self.config_map:
            line = ConfigLine(self, data, use_sizer=False, cbk=config.set_value)
            sizer.Add(line.label, proportion=0, flag=wx.EXPAND)
            sizer.Add(line.widget, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)


class CtlBtnPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        buttons: list[tuple[str, str, Callable[[Any], None]]] = [
            ("删除头像缓存", "也可到heads_cache目录下删除", self.clear_head_cache),
            ("保存数据", "立即保存当前数据到文件", self.save_data_now),
        ]
        sizer = wx.GridSizer(len(buttons), 3, 5, 5)
        for label, tip, cbk in buttons:
            btn = wx.Button(self, label=label)
            btn.SetToolTip(wx.ToolTip(tip))
            btn.Bind(wx.EVT_BUTTON, cbk)
            sizer.Add(btn, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)

    @staticmethod
    def clear_head_cache(_):
        cache_dir = "heads_cache"
        for file_name in os.listdir(cache_dir):
            if file_name.endswith(".png"):
                os.remove(os.path.join(cache_dir, file_name))
        wx.MessageBox("清除成功", "提示", wx.OK | wx.ICON_INFORMATION)

    @staticmethod
    def save_data_now(_):
        if config.enable_data_save:
            msg = common_data.data_manager.save_data()
            if msg:
                wx.MessageBox(msg, "保存错误", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox("保存成功", "提示", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("保存失败, 请先启用保存数据功能", "提示", wx.OK | wx.ICON_INFORMATION)


class ConfigPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.config_line_panel = ConfigLinePanel(self)
        self.ctl_btn_panel = CtlBtnPanel(self)
        sizer.Add(self.config_line_panel, proportion=1, flag=wx.EXPAND)
        sizer.Add(self.ctl_btn_panel, proportion=0, flag=wx.EXPAND)
        self.SetSizer(sizer)
