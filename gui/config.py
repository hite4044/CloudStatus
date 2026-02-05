"""
配置面板
提供 GUI化配置编辑 的GUI定义文件
"""
import os
from copy import copy
# noinspection PyUnresolvedReferences
from dataclasses import dataclass

from gui.events import ApplyValueEvent, EVT_APPLY_VALUE
from gui.widget import *
from lib.common_data import common_data
from lib.config import config, DataSaveFmt, SkinLoadWay, PlayerColorPickWay
from lib.data import MAX_SIZE
from lib.skin import skin_mgr


@dataclass
class ConfigData:
    label: str
    config_key: str
    fmt: type[Any]
    tip: str | None = None
    range: tuple[int | float, int | float] | None = None
    items_desc: dict[Enum, str] | None = None


@dataclass
class ConfigGroup:
    label: str
    lines: list[ConfigData]
    tip: str | None = None


class StaticFlexGridSizer(wx.StaticBoxSizer):
    def __init__(self, parent: wx.Window, label=wx.EmptyString,
                 rows: int = 1, cols: int = 1, vgap: int = 0, hgap: int = 0):
        super().__init__(wx.HORIZONTAL, parent, label)
        self.grid_sizer = wx.FlexGridSizer(rows, cols, vgap, hgap)
        super().Add(self.grid_sizer, 1, wx.EXPAND)

    def Add(self, window: wx.Window, proportion: int = 0, flag: int = 0, border: int = 0):
        self.grid_sizer.Add(window, proportion, flag, border)


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

    def __init__(self, parent: wx.Window, data: ConfigData, use_sizer: bool = True,
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
            keys = [k for k in data.items_desc.keys()]
            self.selection_map: dict[int, Enum] = {i: k for i, k in enumerate(keys)}
            try:
                self.widget.SetSelection(keys.index(self.value))
            except  ValueError:
                self.widget.SetSelection(0)
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
            return self.selection_map[self.widget.GetSelection()]
        else:
            # noinspection PyUnresolvedReferences
            return self.fmt(self.widget.GetValue())


class ConfigLinePanel(wx.SplitterWindow):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        COLOR_PICK_WAY = {
            PlayerColorPickWay.EYE_COLOR: "眼睛颜色 (~1ms)",
            PlayerColorPickWay.MAIN_COLOR: "主颜色 (~50ms)",
            PlayerColorPickWay.SECOND_COLOR: "次颜色 (~50ms)",
            PlayerColorPickWay.CUSTOM_COLOR_INDEX: "自定义颜色索引 (~50ms)",
            PlayerColorPickWay.FIXED_EYE_POS: "固定眼睛位置 (~0ms)",
        }
        self.config_map: list[ConfigData | ConfigGroup] = [
            ConfigData("服务器地址", "addr", str, "要监测的服务器的地址"),
            ConfigGroup("监测", [
                ConfigData("检查间隔", "check_inv", float, "两次检查之间的间隔 (秒)", (5, 600)),
                ConfigData("超时时间", "time_out", float, "获取服务器状态的超时时间 (秒)", (0.5, 6.0)),
                ConfigData("重试次数", "retry_times", int, "获取服务器状态失败的重试次数", (1, 5)),
                ConfigData("保存空数据点", "save_empty_pts", bool, "保存服务器离线时的数据点")
            ]),
            ConfigGroup("数据", [
                ConfigData("启用保存数据功能", "enable_data_save", bool, "一般用于远程路径查看数据"),
                ConfigData("数据文件夹", "data_dir", str, "存放路径点数据文件的文件夹\n需要重新启动程序以生效"),
                ConfigData("点/文件", "points_per_file", int, "每个文件存储的最大数据点数量", (100, 5000)),
                ConfigData("点/保存", "saved_per_points", int, "获取多少个数据点后保存一次数据", (1, 20)),
                ConfigData("数据加载线程数", "data_load_threads", int, "一般越大越快, 推荐 4-8", (1, 32)),
            ]),
            ConfigData("分析最短在线时间", "min_online_time", int,
                       "数据分析时使用的单次最小在线时间\n小于该时间忽略此次在线 (秒)", (0, 600)),
            ConfigData("数据空隙修复间隔", "fix_sep", float,
                       "数据点之间的空隙大于该值时 (秒), 通过增加假数据点(不会保存至磁盘)自动修复",
                       (100, 600)),
            ConfigData("服务器名", "server_name", str, "重启程序生效"),
            ConfigData("数据文件格式", "data_save_fmt", DataSaveFmt,
                       tip="使用新的数据格式, 可以安全地随意切换数据格式 (保存性能有差别)\n下一次保存数据时使用新的格式",
                       items_desc={
                           DataSaveFmt.NORMAL: "普通格式 (速度中等) (100%)",
                           DataSaveFmt.PLAYER_LIST_MAPPING: "玩家列表映射格式 (速度快) (50%)",
                           DataSaveFmt.PLAYER_MAPPING: "玩家映射格式 (速度中等) (36%)",
                       }),
            ConfigGroup("图表", [
                ConfigData("图表线颜色", "plot_line_color", str, "格式为#FFFFFF"),
                ConfigData("图表标签颜色", "plot_fg_color", str, "格式为#FFFFFF"),
                ConfigData("图表网格颜色", "plot_grid_color", str, "格式为#FFFFFF"),
                ConfigData("图表背景颜色", "plot_bg_color", str, "格式为#FFFFFF"),
                ConfigData("图表线宽", "plot_line_width", float, range=(0.1, 5.0)),
                ConfigData("图表线透明度", "plot_line_alpha", float, range=(0.0, 1.0)),
                ConfigData("图表最大缩放", "plot_max_scale", float, range=(1.5, 400.0)),
            ]),
            ConfigGroup("全部玩家", [
                ConfigData("启用获取全部玩家", "enable_full_players", bool, "重复获取服务器状态直到获取到全部玩家名称"),
                ConfigData("FP循环获取间隔", "fp_re_status_inv", float, "重获全部玩家 的间隔", (1.0, 10.0)),
                ConfigData("FP最大重试次数", "fp_max_try", int, "重获全部玩家 的最大重试次数", (2, 7))
            ]),
            ConfigData("记录服务器延迟", "status_ping", bool,
                       "获取服务器信息时是否获取服务器延迟\n减少数据文件大小, 不影响之前的数据\n有极微小的性能提升"),
            ConfigGroup("皮肤", [
                ConfigData("皮肤加载方式", "skin_load_way", SkinLoadWay,
                           tip="指定从哪个皮肤站加载皮肤",
                           items_desc={
                               SkinLoadWay.MOJANG: "正版皮肤",
                               SkinLoadWay.LITTLE_SKIN: "LittleSkin",
                           }),
                ConfigData("自定义皮肤服务器", "custom_skin_server", str, "皮肤服务器的地址, 需支持CustomSkinLoader"),
                ConfigData("自定义皮肤根目录", "custom_skin_root", str,
                           "皮肤服务器用户资料的皮肤字典路径, 一般为 skins\n"
                           "或自己获取: 访问[https://{皮肤服务器地址}/{角色名}.json]并查看default关键字(贴图ID)所在字典名"),

            ]),
            ConfigGroup("界面", [
                ConfigData("启用在线时间段列表", "gui_use_online_range_list", bool,
                           "在在线时间分析窗口显示玩家在线在线时间段列表"),
                ConfigData("玩家卡片取色方式", "player_card_pick_way", PlayerColorPickWay,
                           "在总览界面的 玩家卡片背景颜色的取色方式", items_desc=COLOR_PICK_WAY),
                ConfigData("分析窗口取色方式", "player_win_pick_way", PlayerColorPickWay,
                           "在玩家在线分析窗口中, 背景颜色的取色方式", items_desc=COLOR_PICK_WAY),
                ConfigData("头像颜色提取数量", "color_extract_num", int,
                           "提取头像主色时提取的颜色数量", range=(1, 10)),
                ConfigData("头像颜色提取质量", "color_extract_quality", int,
                           "提取头像主色时的质量", range=(10, 100)),
                ConfigData("颜色列表索引-左", "extracted_color_index", int,
                           "选择头像中提取的颜色列表中的哪个颜色作为主题色\n-1 表示倒数第一个", range=(1, 10)),
                ConfigData("颜色列表索引-右", "extracted_color_index2", int,
                           "选择头像中提取的颜色列表中的哪个颜色作为主题色\n-1 表示倒数第一个", range=(1, 10)),
                ConfigData("固定眼睛位置 X", "eye_fixed_pos_x", int,
                           "固定眼睛位置的 X 坐标", range=(0, 8)),
                ConfigData("固定眼睛位置 Y", "eye_fixed_pos_y", int,
                           "固定眼睛位置的 Y 坐标", range=(0, 8)),
            ]),
            ConfigGroup("调试选项", [
                ConfigData("输出眼睛取色日志", "debug_output_skin_color_pick_log", bool,
                           "在通过算法选择皮肤眼睛颜色时, 输出对应权重日志"),

            ])
        ]
        line_panel = wx.Panel(self)
        groups_panel = wx.Panel(self)
        line_sizer = wx.FlexGridSizer(len(self.config_map) + 1, 2, 5, 5)
        groups_sizer = wx.FlexGridSizer(10, 1, 5, 5)
        self.SetFont(ft(11))
        line_sizer.AddSpacer(5)
        line_sizer.AddSpacer(0)

        def load_config(t_sizer: wx.Sizer, data: ConfigData | ConfigGroup, config_parent: wx.Window):
            if isinstance(data, ConfigGroup):
                group_panel = wx.CollapsiblePane(groups_panel, label=data.label,
                                                 style=wx.CP_DEFAULT_STYLE | wx.CP_NO_TLW_RESIZE)
                group_sizer_out = wx.BoxSizer(wx.VERTICAL)
                group_sizer = wx.FlexGridSizer(len(data.lines), 2, 5, 5)
                for cfg_data_in in data.lines:
                    load_config(group_sizer, cfg_data_in, group_panel.GetPane())
                group_sizer_out.Add(group_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
                group_panel.GetPane().SetSizer(group_sizer_out)
                group_panel.Collapse(True)
                group_panel.Bind(wx.EVT_COLLAPSIBLEPANE_CHANGED, self.on_collapse)
                groups_sizer.Add(group_panel, 1, wx.EXPAND)
            if isinstance(data, ConfigData):
                line = ConfigLine(config_parent, data, use_sizer=False, cbk=config.set_value)
                t_sizer.Add(line.label, proportion=0, flag=wx.EXPAND)
                t_sizer.Add(line.widget, proportion=1, flag=wx.EXPAND)

        for cfg_data in self.config_map:
            load_config(line_sizer, cfg_data, line_panel)

        line_panel.SetSizer(line_sizer)
        groups_panel.SetSizer(groups_sizer)
        self.SetMinimumPaneSize(20)
        self.SplitVertically(line_panel, groups_panel)
        self.SetSashGravity(0.5)

        self.groups_sizer = groups_sizer

    def on_collapse(self, event: wx.CollapsiblePaneEvent):
        self.groups_sizer.Layout()
        event.Skip()


class CtlBtnPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        buttons: list[tuple[str, str, Callable[[Any], None]]] = [
            ("删除缓存", "也可删除cache目录, 主要是缓存的皮肤和头像", self.clear_cache),
            ("保存数据", "立即保存当前数据到文件", self.save_data_now),
            ("保存缓存状态", "立即保存皮肤缓存状态到文件", self.save_skin_status)
        ]
        sizer = wx.FlexGridSizer(10, 2, 5, 5)
        for label, tip, cbk in buttons:
            btn = wx.Button(self, label=label)
            btn.SetToolTip(wx.ToolTip(tip))
            btn.Bind(wx.EVT_BUTTON, cbk)
            sizer.Add(btn, 0, wx.EXPAND)
        self.SetSizer(sizer)

    @staticmethod
    def clear_cache(_):
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

    @staticmethod
    def save_skin_status(_):
        skin_mgr.save_cache()
        wx.MessageBox("保存成功", "提示", wx.OK | wx.ICON_INFORMATION)


class ConfigPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.config_line_panel = ConfigLinePanel(self)
        self.ctl_btn_panel = CtlBtnPanel(self)
        sizer.Add(self.config_line_panel, proportion=1, flag=wx.EXPAND)
        sizer.AddSpacer(5)
        sizer.Add(wx.StaticLine(self, style=wx.LI_VERTICAL), 0, wx.EXPAND)
        sizer.AddSpacer(5)
        sizer.Add(self.ctl_btn_panel, proportion=0, flag=wx.EXPAND)
        self.SetSizer(sizer)
