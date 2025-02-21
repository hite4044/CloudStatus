"""
配置面板
提供 GUI化配置编辑 的GUI定义文件
"""
from typing import Any, Callable

from gui.widget import *
from lib.config import config
from lib.data import MAX_SIZE


class ConfigLine(wx.Panel):
    """用作配置修改"""

    def __init__(self, parent: wx.Window, label: str, value: Any, fmt: type[Any], use_sizer: bool = True,
                 key: str = None,
                 cbk: Callable[[str, Any], None] = None):
        if use_sizer:
            super().__init__(parent)
            parent = self

        self.label = label
        self.value = value
        self.fmt = fmt
        self.key = key
        self.cbk = cbk
        self.last_value = str(self.value)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.label = CenteredText(parent, label=self.label, x_center=False)
        if self.fmt == str:
            self.widget = wx.TextCtrl(parent, value=self.value, style=wx.TE_PROCESS_ENTER)
        elif self.fmt == int:
            self.widget = wx.SpinCtrl(parent, value=str(self.value), max=maxsize, style=wx.TE_PROCESS_ENTER)
        elif self.fmt == float:
            self.widget = wx.SpinCtrlDouble(parent, value=str(self.value), max=maxsize, style=wx.TE_PROCESS_ENTER)
        elif self.fmt == bool:
            self.widget = wx.CheckBox(parent)
            self.widget.SetValue(self.value)
        else:
            raise ValueError(f"Unsupported fmt: {self.fmt}")
        # self.label.SetMaxSize((-1, 28))
        self.widget.SetMaxSize((MAX_SIZE[0], 28))
        self.widget.SetMinSize((MAX_SIZE[0], 28))
        if use_sizer:
            sizer.Add(self.label, proportion=0)
            sizer.Add(self.widget, flag=wx.EXPAND, proportion=1)
            self.SetSizer(sizer)
            self.SetMaxSize((-1, 28))
        self.widget.Bind(wx.EVT_SET_FOCUS, self.focus_in)
        if self.fmt == bool:
            self.widget.Bind(wx.EVT_CHECKBOX, self.apply_value)
        else:
            self.widget.Bind(wx.EVT_KILL_FOCUS, self.apply_value)
            self.widget.Bind(wx.EVT_TEXT_ENTER, self.apply_value)

    def focus_in(self, event: wx.Event):
        self.last_value = self.widget.GetValue()
        event.Skip()

    def apply_value(self, event: wx.Event):
        try:
            self.cbk(self.key, self.get_value())
        except ValueError as e:
            self.widget.SetValue(self.last_value)
            wx.MessageBox(str(e), "配置应用错误", wx.OK | wx.ICON_ERROR)
        if isinstance(event, wx.FocusEvent):
            event.Skip()

    def get_value(self) -> Any:
        return self.fmt(self.widget.GetValue())


class StringLine(ConfigLine):
    def __init__(self, parent: wx.Window, label: str, value: str):
        super().__init__(parent, label, value, fmt=str)


class IntLine(ConfigLine):
    def __init__(self, parent: wx.Window, label: str, value: int):
        super().__init__(parent, label, value, fmt=int)


class FloatLine(ConfigLine):
    def __init__(self, parent: wx.Window, label: str, value: float):
        super().__init__(parent, label, value, fmt=float)


class ConfigPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.config_map = {
            "addr": ["地址", str, config.addr],
            "check_inv": ["检查间隔", float, config.check_inv],
            "points_per_file": ["点/文件", int, config.points_per_file],
            "saved_per_points": ["点/保存", int, config.saved_per_points],
            "min_online_time": ["最小在线时间", int, config.min_online_time],
            "fix_sep": ["数据空隙修复间隔", float, config.fix_sep],
            "data_dir": ["数据文件夹", str, config.data_dir],
            "enable_data_save": ["启用保存数据功能", bool, config.enable_data_save]
        }
        sizer = wx.FlexGridSizer(len(self.config_map) + 1, 2, 5, 5)
        self.SetFont(ft(11))
        for key, (label, fmt, value) in self.config_map.items():
            line = ConfigLine(self, label, value, fmt, False, key, config.set_value)
            sizer.Add(line.label, proportion=0, flag=wx.EXPAND)
            sizer.Add(line.widget, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)
