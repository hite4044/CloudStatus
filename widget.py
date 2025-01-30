from typing import Any, Callable

import wx

font_cache: dict[int, wx.Font] = {}
maxsize = 1919810
ssEVT_FILTER_CHANGE = wx.NewEventType()
EVT_FILTER_CHANGE = wx.PyEventBinder(ssEVT_FILTER_CHANGE)


# noinspection PyPep8Naming
class FilterChangeEvent(wx.PyCommandEvent):
    def __init__(self, filter_: Any):
        wx.PyCommandEvent.__init__(self, ssEVT_FILTER_CHANGE, wx.ID_ANY)
        self.filter = filter_


def ft(size: int):
    if size not in font_cache:
        font_cache[size] = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font_cache[size].SetPointSize(size)
    return font_cache[size]


class ConfigLine(wx.Panel):
    """用作配置修改"""

    def __init__(self, parent: wx.Window, label: str, value: Any, fmt: type[Any], key: str = None,
                 cbk: Callable[[str, Any], None] = None):
        super().__init__(parent)
        self.label = label
        self.value = value
        self.fmt = fmt
        self.key = key
        self.cbk = cbk
        self.last_value = str(self.value)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.label = CenteredStaticText(self, label=self.label, x_center=False)
        if self.fmt == str:
            self.widget = wx.TextCtrl(self, value=self.value, style=wx.TE_PROCESS_ENTER)
        elif self.fmt == int:
            self.widget = wx.SpinCtrl(self, value=str(self.value), max=maxsize, style=wx.TE_PROCESS_ENTER)
        elif self.fmt == float:
            self.widget = wx.SpinCtrlDouble(self, value=str(self.value), max=maxsize, style=wx.TE_PROCESS_ENTER)
        else:
            raise ValueError(f"Unsupported fmt: {self.fmt}")
        self.label.SetMinSize((-1, 28))
        sizer.Add(self.label, proportion=0)
        sizer.Add(self.widget, flag=wx.EXPAND, proportion=1)
        self.SetSizer(sizer)
        self.SetMaxSize((-1, 28))
        self.widget.Bind(wx.EVT_SET_FOCUS, self.focus_in)
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
