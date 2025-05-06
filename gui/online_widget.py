from copy import copy
# noinspection PyUnresolvedReferences
from dataclasses import dataclass, field
from threading import Thread
from time import localtime, strftime
from typing import cast

from gui.widget import *
from lib.common_data import common_data
from lib.config import config
from lib.data import Player
from lib.log import logger
from lib.skin import skin_mgr, HeadLoadData

XLIM_WIDTH = 35
YLIM_WIDTH = 55
AXIS_STEP_WIDTH = 120
TEXT_OFFSET_X = -4
TEXT_OFFSET_Y = -11
DATA_PAD_X = 30
DATA_PAD_Y = 0.08
XLIM_COLOR = wx.Colour(128, 128, 128)
YLIM_COLOR = wx.Colour(0, 0, 0)
DATA_LINE_COLOR = wx.Colour(48, 173, 201)
DATA_LINE_WIDTH = 3


def fmt_time_unit(seconds: float, day: bool = False, hour: bool = False, minute: bool = True, flag=False) -> str:
    time_tuple = tuple_fmt_time(seconds)
    text = ""
    if day:
        if (not hour and not minute) or time_tuple[0] != 0:
            text += f"{time_tuple[0]}d"
    if hour:
        if not minute or time_tuple[1] != 0:
            if flag:
                text += f"{seconds / 3600:.1f}h"
            else:
                text += f"{time_tuple[1]}h"
    if minute:
        text += f"{time_tuple[2]}m"
    return text


@dataclass
class EyeResampleRule:
    eye_pos: tuple[int, int]
    resample_points: list[tuple[int, int]]
    res_resample_points: list[tuple[int, int]] = field(default_factory=list)


class TimeOnlinePlotUnit(Enum):
    DAY = 0
    WEEK = 1
    MONTH = 2
    CUSTOM = 3


PLOT_PREDEFINE = {
    TimeOnlinePlotUnit.DAY: (timedelta(hours=1), timedelta(days=1), 24),
    TimeOnlinePlotUnit.WEEK: (timedelta(days=1), timedelta(weeks=1), 7),
    TimeOnlinePlotUnit.MONTH: (timedelta(weeks=1), timedelta(days=30), 5),
    TimeOnlinePlotUnit.CUSTOM: (timedelta(days=1), timedelta(days=1), 1),
}


class TimeFilter:
    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end

    def filter(self, start: float, end: float) -> tuple[float, float] | None:
        """过滤掉超出范围的时间段, 返回截断的时间片段"""
        if start < self.start:
            start = self.start
        elif start > self.end:
            start = self.end
        if end > self.end:
            end = self.end
        elif end < self.start:
            end = self.start
        if start == end:
            return None
        return start, end


class DataPlot(wx.Window):
    def __init__(self, parent: wx.Window, datas: list[float], times: list[float]):
        super().__init__(parent, style=wx.TRANSPARENT_WINDOW, name='DataPlotPlot')
        self.max_data = max(datas)
        if self.max_data == 0:
            self.max_data = 2
        self.datas = datas
        self.times = times
        self.grid: bool = True
        self.tooltip = ToolTip(self, "")
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_MOTION, self.update_tooltip)

    def update_tooltip(self, event: wx.MouseEvent):
        """实现鼠标查看数据"""
        width, height = self.GetClientSize()
        width -= YLIM_WIDTH
        x = event.GetX() - YLIM_WIDTH
        index = int(x / width * len(self.datas))
        if not 0 <= index < len(self.datas):
            self.tooltip.set_tip("")
            return
        self.tooltip.set_tip(self.get_tip_text(index, self.datas[index]))

    def on_paint(self, _):
        try:
            dc = wx.PaintDC(self)
        except RuntimeError:
            return
        scale = self.draw_axis(dc)
        self.draw_data(dc, scale)

    def draw_data(self, dc: wx.PaintDC, scale: float):
        width, height = self.GetClientSize()
        plot_width, plot_height = width - YLIM_WIDTH - 2 * DATA_PAD_X, height - XLIM_WIDTH
        datas_len = len(self.datas) - 1
        black_pen = wx.Pen(wx.Colour(0, 0, 0))
        data_line_pen = wx.Pen(DATA_LINE_COLOR, width=DATA_LINE_WIDTH)
        dc.SetPen(black_pen)
        dc.DrawLine(YLIM_WIDTH, plot_height, width, plot_height)  # 绘制水平坐标轴

        # 绘制刻度+标签
        for i, data in enumerate(self.datas):
            x_position = int(i * plot_width / datas_len) + YLIM_WIDTH + DATA_PAD_X

            dc.SetPen(wx.Pen(XLIM_COLOR, style=wx.PENSTYLE_DOT))  # 设置 图表垂直刻度 颜色
            dc.DrawLine(x_position, 0, x_position, plot_height)  # 绘制 图表垂直刻度
            dc.SetPen(black_pen)  # 设置 水平坐标轴刻度 颜色
            dc.DrawLine(x_position, plot_height, x_position, plot_height + 5)  # 绘制 水平坐标轴刻度
            text = self.get_xlim_label(self.times[i])  # 获取标签文字
            text_width, _ = dc.GetTextExtent(text)
            dc.DrawText(text, int(x_position - text_width / 2), plot_height + 5)  # 绘制 水平坐标轴刻度标签

        # 绘制数据连线
        last_pt = None
        offset_y = DATA_PAD_Y * self.max_data * scale
        plot_height -= int(offset_y * 2)
        dc.SetPen(data_line_pen)
        for i, data in enumerate(self.datas):
            x_position = int(i * plot_width / datas_len) + YLIM_WIDTH + DATA_PAD_X
            y_position = int(plot_height - (data * scale) + offset_y)
            if last_pt is not None:
                dc.DrawLine(last_pt[0], last_pt[1], x_position, y_position)  # 绘制数据连线
            last_pt = (x_position, y_position)

        # 绘制数据点+标签
        dc.SetPen(black_pen)
        for i, data in enumerate(self.datas):
            x_position = int(i * plot_width / datas_len) + YLIM_WIDTH + DATA_PAD_X
            y_position = int(plot_height - (data * scale) + offset_y)

            dc.DrawCircle(x_position, y_position, 3)  # 绘制数据点
            text = self.get_data_label(data)  # 获取数据标签文字
            text_width, text_height = dc.GetTextExtent(text)
            dc.DrawText(text, int(x_position - text_width / 2), int(y_position - text_height - 5))  # 绘制数据标签

    def draw_axis(self, dc: wx.PaintDC):
        # 绘制垂直坐标轴
        width, height = self.GetClientSize()
        max_data = self.max_data * (1 + DATA_PAD_Y * 2)
        step, step_width = self.get_step(max_data, height - XLIM_WIDTH)
        ylim_height = height - XLIM_WIDTH
        dc.DrawLine(YLIM_WIDTH, 0, YLIM_WIDTH, ylim_height)
        dc.DrawLine(YLIM_WIDTH, 0, width, 0)
        dc.DrawLine(width - 1, 0, width - 1, height - XLIM_WIDTH)

        scale = step_width / step
        ylim_pen = wx.Pen(YLIM_COLOR)
        offset_y = DATA_PAD_Y * self.max_data  # 数据偏移量, 用来修正 偏移过的数据值
        if all([x == 0.0 for x in self.datas]):  # 特殊: 数据全0
            y_position = int(ylim_height - offset_y * scale)
            text = self.get_ylim_label(0)
            dc.SetPen(ylim_pen)
            dc.DrawLine(YLIM_WIDTH - 5, y_position, width, y_position)  # 绘制Y轴刻度 (包含图表内部的)
            text_width = dc.GetTextExtent(text)[0]
            dc.DrawText(text, YLIM_WIDTH - 5 + TEXT_OFFSET_X - text_width, y_position + TEXT_OFFSET_Y)  # 绘制标签
            return step_width / step

        for i, data_off in enumerate(range(int(offset_y), int(max_data + offset_y) + step, step)):  # 数据整体向上偏移
            # 当 [水平刻度线距顶部太近]或[水平刻度线超过顶部]，则把刻度线限制在顶部稍下
            if data_off > max_data or max_data - data_off < 8 / scale:
                if data_off * scale - ylim_height > step_width / 2:  # 刻度线距离顶部太远, 跳过绘制
                    continue
                y_position = 8
                data_off = (ylim_height - 8) / scale  # 根据绘制的坐标反推出数据值
                text = self.get_ylim_label(round(data_off - offset_y))  # 获取Y轴刻度标签
            else:
                y_position = int(ylim_height - (data_off * scale))
                text = self.get_ylim_label(round(data_off - offset_y) if i != 0 else 0)  # 获取Y轴刻度标签

            dc.SetPen(ylim_pen)
            dc.DrawLine(YLIM_WIDTH - 5, y_position, width, y_position)  # 绘制Y轴刻度 (包含图表内部的)
            text_width = dc.GetTextExtent(text)[0]
            dc.DrawText(text, YLIM_WIDTH - 5 + TEXT_OFFSET_X - text_width, y_position + TEXT_OFFSET_Y)  # 绘制标签

        return step_width / step

    @staticmethod
    def get_step(data: float, length: int) -> tuple[int, int]:
        step = max(int(data / (length / AXIS_STEP_WIDTH)), 1)
        step_width = int(length / (data / step))
        return step, step_width

    @staticmethod
    def get_data_label(data: float):
        return f"{data:.2f}"

    @staticmethod
    def get_tip_text(index: int, data: float):
        return f"索引: {index}\n数据: {data:.2f}"

    @staticmethod
    def get_ylim_label(data: float):
        return str(int(data))

    @staticmethod
    def get_xlim_label(timestamp: float):
        return datetime.fromtimestamp(timestamp).strftime("%H:%M")


class PlayerTimeOnlinePlot(DataPlot):
    def __init__(self, parent: wx.Window, player: str, unit: TimeOnlinePlotUnit):
        datas, times = self.load_data(player, unit)
        self.unit = unit
        self.start_dt = datetime.now()
        self.end_dt = datetime.now()
        self.step_delta, _, _ = PLOT_PREDEFINE[unit]
        super().__init__(parent, datas, times)

    def get_time_str(self, data: float):
        if self.unit == TimeOnlinePlotUnit.DAY:
            return fmt_time_unit(data)
        elif self.unit == TimeOnlinePlotUnit.WEEK:
            return fmt_time_unit(data, hour=True, minute=True)
        else:
            return fmt_time_unit(data, day=True, hour=True, minute=False, flag=True)

    def get_data_label(self, data: float):
        return self.get_time_str(data)

    def get_tip_text(self, index: int, data: float):
        data_text = self.get_time_str(data)
        range_start_dt = self.start_dt + self.step_delta * index
        range_end_dt = range_start_dt + self.step_delta
        if self.unit == TimeOnlinePlotUnit.DAY:
            rng = f"{range_start_dt.strftime('%H:00')}"
        elif self.unit == TimeOnlinePlotUnit.WEEK:
            rng = f"{range_start_dt.strftime('%m-%d')}"
        else:
            rng = f"{range_start_dt.strftime('%m-%d')} -> {range_end_dt.strftime('%m-%d')}"
        return f"时间段: {rng}\n在线时间: {data_text}"

    def get_ylim_label(self, data: float):
        if self.unit == TimeOnlinePlotUnit.DAY:
            return fmt_time_unit(data)
        elif self.unit == TimeOnlinePlotUnit.WEEK:
            return fmt_time_unit(data, hour=True, minute=False)
        else:
            return fmt_time_unit(data, day=True, hour=True, minute=False)

    def get_xlim_label(self, timestamp: float):
        dt_obj = datetime.fromtimestamp(timestamp)
        if self.unit == TimeOnlinePlotUnit.DAY:
            return f"{dt_obj.hour}:00"
        else:
            return f"{dt_obj.strftime('%m-%d')}"

    def load_data(self, player: str, unit: TimeOnlinePlotUnit) -> tuple[list[float], list[float]]:
        step_delta, total, count = copy(PLOT_PREDEFINE[unit])
        step_delta = step_delta.seconds + step_delta.days * 24 * 60 * 60
        end_dt = datetime.now()
        start_dt = end_dt - total
        self.start_dt = start_dt
        self.end_dt = end_dt
        self.step_delta = step_delta
        time_filter = TimeFilter(start_dt.timestamp(), end_dt.timestamp())
        time_ranges = []
        for time_range in common_data.data_manager.get_player_online_ranges(player):
            if t_range := time_filter.filter(*time_range):
                time_ranges.append(t_range)

        time_datas: dict[int, float] = {i: 0 for i in range(count)}

        def proc_range(start: float, end: float):
            index = int((start - self.start_dt.timestamp()) / step_delta)
            if index not in time_datas:
                time_datas[index] = 0
            time_datas[index] += end - start

        start_timestamp = start_dt.timestamp()
        for time_range in time_ranges:
            start_delta = int((time_range[0] - start_timestamp) / step_delta)
            end_delta = int((time_range[1] - start_timestamp) / step_delta)
            if start_delta != end_delta:
                proc_range(time_range[0], start_timestamp + (start_delta + 1) * step_delta)
                proc_range(start_timestamp + end_delta * step_delta, time_range[1])
            else:
                proc_range(time_range[0], time_range[1])

        times = [start_dt.timestamp() + i * step_delta for i in time_datas.keys()]
        return list(time_datas.values()), times


class PlayerTimeOnlinePlotGroup(wx.Panel):
    def __init__(self, parent: wx.Window, player: str):
        super().__init__(parent, style=wx.TRANSPARENT_WINDOW)
        self.player = player
        self.plots: list[PlayerTimeOnlinePlot] = []
        self.title = CenteredText(self, label=f"在线时长统计", x_center=False)
        self.switch_cb = wx.Choice(self, choices=["最近一天", "最近一周", "最近一个月", "自定义"])
        self.notebook = NoTabNotebook(self)
        self.title.SetFont(ft(20))
        title_bar = wx.BoxSizer(wx.HORIZONTAL)
        sizer = wx.BoxSizer(wx.VERTICAL)
        title_bar.Add(self.title, 1, wx.EXPAND)
        title_bar.Add(self.switch_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(title_bar, 0, wx.EXPAND)
        sizer.AddSpacer(7)
        sizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sizer)

        for unit in [TimeOnlinePlotUnit.DAY, TimeOnlinePlotUnit.WEEK, TimeOnlinePlotUnit.MONTH]:
            plot = PlayerTimeOnlinePlot(self.notebook, player, unit)
            self.plots.append(plot)
            self.notebook.add_page(plot)

        self.switch_cb.Bind(wx.EVT_CHOICE, self.on_switch_page)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.switch_cb.SetSelection(1)
        self.on_switch_page(None)

    def on_switch_page(self, _):
        selection = self.switch_cb.GetSelection()
        if selection == 3:
            dialog = NumberInputDialog(self, "输入时间范围", [IntEntryCfg("天数:", 10), IntEntryCfg("计算间隔(天)", 1)])
            if dialog.ShowModal() != wx.ID_OK:
                return
            days, interval = dialog.get_values()
            count = int(days / interval) + 1 if float(int(days / interval)) != days / interval else 0
            PLOT_PREDEFINE[TimeOnlinePlotUnit.CUSTOM] = (timedelta(days=interval), timedelta(days=days), count)
            plot = PlayerTimeOnlinePlot(self.notebook, self.player, TimeOnlinePlotUnit.CUSTOM)
            if len(self.plots) > 3:
                self.notebook.remove_page(3)
                del self.plots[3]
            self.plots.append(plot)
            self.notebook.add_page(plot)
        self.notebook.switch_page(selection)
        self.GetParent().Refresh()


class PlayerOnlineRangeList(wx.ListCtrl):
    def __init__(self, parent: wx.Window, player: str):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_VIRTUAL, size=(510, -1))
        self.ranges = []
        self.player = player
        self.SetItemCount(1)
        self.InsertColumn(1, "序号", format=wx.LIST_FORMAT_CENTER, width=50)
        self.AppendColumn("加入", format=wx.LIST_FORMAT_CENTER, width=150)
        self.AppendColumn("离开", format=wx.LIST_FORMAT_CENTER, width=150)
        self.AppendColumn("持续", format=wx.LIST_FORMAT_CENTER, width=140)
        Thread(target=self.load_data, daemon=True).start()

    def load_data(self):
        self.ranges = common_data.data_manager.get_player_online_ranges(self.player)
        wx.CallAfter(self.SetItemCount, len(self.ranges))

    def OnGetItemText(self, item: int, column: int):
        if column == 0:
            return str(item + 1)
        elif column == 1:
            return strftime("%y-%m-%d %H:%M:%S", localtime(self.ranges[item][0]))
        elif column == 2:
            return strftime("%y-%m-%d %H:%M:%S", localtime(self.ranges[item][1]))
        elif column == 3:
            return string_fmt_time(self.ranges[item][1] - self.ranges[item][0])
        return "Unknow"


class PlayerDayOnlinePlot(wx.Window):
    """玩家逐小时在线图表"""

    def __init__(self, parent: wx.Window, player: str):
        super().__init__(parent, id=wx.ID_ANY, pos=wx.DefaultPosition, style=wx.TRANSPARENT_WINDOW,
                         name='PlayerDayOnlinePlot')
        self.player = player
        self.datas: list[float] = [0.1, 0.4, 0.9, 1.0, 0.1, 0.6]
        Thread(target=self.load_hour_online_data, args=(player,), daemon=True).start()
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.tooltip = ToolTip(self, "")

    def load_hour_online_data(self, player: str):
        """处理出玩家每小时在线的占比"""
        new_data = {i: 0 for i in range(24)}
        ranges = common_data.data_manager.get_player_online_ranges(player)
        days = set()
        for start, end in ranges:
            start_date = datetime.fromtimestamp(start)
            end_date = datetime.fromtimestamp(end)
            if start_date.hour == end_date.hour:
                new_data[start_date.hour] += end - start
                days.add(str(start_date.date()))
            else:
                offset_time = datetime.fromtimestamp(start).replace(minute=0, second=0, microsecond=0)
                while True:
                    days.add(str(offset_time.date()))
                    if offset_time == start_date.replace(minute=0, second=0, microsecond=0):
                        new_end = timedelta(hours=1) + start_date.replace(minute=0, second=0, microsecond=0)
                        try:
                            new_data[offset_time.hour] += new_end.timestamp() - start_date.timestamp()
                        except OSError:
                            new_end.timestamp()
                            start_date.timestamp()
                            new_end.timestamp() - start_date.timestamp()
                            new_data[offset_time.hour] += new_end.timestamp() - start_date.timestamp()
                            return
                    elif offset_time == end_date.replace(minute=0, second=0, microsecond=0):
                        new_start = end_date.replace(minute=0, second=0, microsecond=0)
                        new_data[offset_time.hour] += end_date.timestamp() - new_start.timestamp()
                        break
                    else:
                        new_data[offset_time.hour] += 3600
                    offset_time = timedelta(hours=1) + offset_time
        new_data = {i: new_data[i] / len(days) / 3600 for i in range(24)}
        wx.CallAfter(self.set_hour_online_data, list(new_data.values()))

    def set_hour_online_data(self, data: list[float]):
        self.datas = data
        self.Refresh()

    def on_mouse_move(self, event: wx.MouseEvent):
        """实现鼠标查看在线几率数据"""
        width, height = self.GetClientSize()
        x = event.GetX()
        hour = int(x / width * len(self.datas))
        if not 0 <= hour < len(self.datas):
            self.tooltip.set_tip("")
            return
        text = f"时间: {hour}:00-{hour + 1}:00\n数据: {(self.datas[hour] / sum(self.datas)) * 100:.2f}%"
        self.tooltip.set_tip(text)

    def on_paint(self, _):
        try:
            dc = wx.PaintDC(self)
        except RuntimeError:
            return
        dc.SetPen(wx.Pen('#d4d4d4'))  # 设置边框颜色

        dc.SetBrush(wx.Brush('#c56c00'))  # 设置填充颜色
        width, height = self.GetClientSize()
        for i in range(len(self.datas)):
            dc.DrawRectangle(int(width * i / len(self.datas)) + 2, int(height * (1 - self.datas[i])),
                             int(width / len(self.datas)) - 2, int(height * self.datas[i]))


def get_color_similarity(color1: tuple[int, int, int], color2: tuple[int, int, int]):
    """计算颜色相似度, 值越大相似度越小"""
    sim = sum(abs(c1 - c2) for c1, c2 in zip(color1, color2)) / 3 / 255
    return min(sim, 0.5)


def get_eye_color(head: Image.Image):
    """对预设的可能得眼睛位置的周围像素计算相似度, 取相似度和最大的一组眼睛位置"""
    pt_size = head.height / 8

    def debug(msg: str):
        if config.debug_output_skin_color_pick_log:
            logger.debug(msg)

    def get_pixel(x_pos: int, y_pos: int):
        return head.getpixel((int(x_pos * pt_size + pt_size / 2), int(y_pos * pt_size + pt_size / 2)))[:3]

    rules: list[tuple[float, list[EyeResampleRule]]] = [
        (2.5, [EyeResampleRule((2, 5), [(1, 5), (2, 7)]),
               EyeResampleRule((5, 5), [(6, 5), (5, 7)])]),
        (2.0, [EyeResampleRule((2, 6), [(1, 6), (2, 7)], [(2, 5)]),
               EyeResampleRule((5, 6), [(4, 6), (5, 7)], [(5, 5)])]),
        (1.5, [EyeResampleRule((2, 4), [(1, 4), (3, 4)], [(2, 6)]),
               EyeResampleRule((5, 4), [(4, 4), (6, 4)], [(2, 6)])]),
        (0.8, [EyeResampleRule((1, 5), [(0, 5), (2, 5), (1, 6)]),
               EyeResampleRule((6, 5), [(5, 5), (7, 5), (6, 6)])]),
    ]

    results: dict[float, tuple[tuple[int, int, int], tuple[int, int, int]]] = {}
    for widget, rule_group in rules:
        eye_colors = []
        eys_similarities = []
        for eye_rule in rule_group:
            near_similarities = []
            res_near_similarities = [] if eye_rule.res_resample_points else [0.0]
            eye_color = cast(tuple[int, int, int], get_pixel(*eye_rule.eye_pos))
            # 添加调试输出：当前处理的坐标和原始颜色值
            debug(f"|- 处理眼睛 {eye_rule.eye_pos} - 基础颜色: {eye_color}")
            for near_point in eye_rule.resample_points:
                resample_color = cast(tuple[int, int, int], get_pixel(*near_point))
                sim = get_color_similarity(eye_color, resample_color)
                debug(f"   |- 采样点 {near_point} - 颜色: {resample_color} - 相似度: {sim}")
                near_similarities.append(sim)
            for near_point in eye_rule.res_resample_points:
                resample_color = cast(tuple[int, int, int], get_pixel(*near_point))
                sim = get_color_similarity(eye_color, resample_color)
                debug(f"   |- 反向 *采样点 {near_point} - 颜色: {resample_color} - 相似度: {sim}")
                res_near_similarities.append(sim)
            # 添加调试输出：匹配结果
            eye_sim = sum(near_similarities) / len(near_similarities) - sum(res_near_similarities) / len(
                res_near_similarities)
            debug(f" |- 眼睛采样点 {eye_rule.eye_pos} - 值: {eye_sim}")
            eye_colors.append(eye_color)
            eys_similarities.append(eye_sim)
        assert len(eye_colors) == 2
        final_sim = max(eys_similarities) * widget
        results[final_sim] = cast(tuple[tuple[int, int, int], tuple[int, int, int]], tuple(eye_colors))
        # 添加调试输出：记录当前结果
        debug(f"# 本组眼睛颜色: {tuple(eye_colors)} - 最终相似度: {final_sim}")
        debug("")

    # 添加最终结果的调试输出
    debug(f"最终选择颜色: {results[max(results.keys())]}")
    return results[max(results.keys())]


class PlayerOnlineWin(wx.Frame):
    """
    一个查看玩家在线时间分析的窗口
    """

    def __init__(self, parent: wx.Window, player: str):
        wx.Frame.__init__(self, parent, title=f"{player} 在线分析", size=(1220, 750))
        self.SetFont(parent.GetFont())
        self.player = player
        self.head = CenteredBitmap(self)
        self.name_label = TransparentCenteredText(self, label=player, size=(-1, 45))
        self.plot = PlayerDayOnlinePlot(self, player)
        self.data_plot = PlayerTimeOnlinePlotGroup(self, player)
        self.ranges_lc = PlayerOnlineRangeList(self, player)
        self.set_best_font_size()
        self.bg_binder = GradientBgBinder(self)
        self.bg_binder.set_color(self.GetBackgroundColour())

        Thread(target=self.load_head, daemon=True).start()

        hor_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ver_sizer = wx.BoxSizer(wx.VERTICAL)
        ver_sizer.Add(self.head, 0, wx.EXPAND)
        ver_sizer.AddSpacer(5)
        ver_sizer.Add(self.name_label, 0, wx.EXPAND)
        ver_sizer.AddSpacer(5)
        ver_sizer.Add(self.plot, 2, wx.EXPAND)
        ver_sizer.AddSpacer(5)
        ver_sizer.Add(self.data_plot, 5, wx.EXPAND)
        hor_sizer.Add(ver_sizer, 2, wx.EXPAND)
        hor_sizer.AddSpacer(5)
        hor_sizer.Add(self.ranges_lc, 1, wx.EXPAND)
        out_sizer = wx.BoxSizer(wx.HORIZONTAL)
        out_sizer.Add(hor_sizer, 1, wx.EXPAND | wx.ALL, 7)
        self.SetSizer(out_sizer)

    def set_best_font_size(self):
        dc = wx.ClientDC(self.name_label)
        ft_size = 25
        while True:
            dc.SetFont(ft(ft_size))
            size = dc.GetTextExtent(self.name_label.GetLabel())
            if size[0] > 180:
                ft_size -= 1
            else:
                break
        self.name_label.SetFont(ft(ft_size))

    def set_icon(self, head: wx.Image):
        self.SetIcon(wx.Icon(head.ConvertToBitmap(-1)))

    def load_card_color(self, head: Image.Image):
        """从玩家头像中提取两个眼睛的颜色并应用到控件中"""
        left_eye, right_eye = get_eye_color(head)
        color_left, color_right = EasyColor(*left_eye), EasyColor(*right_eye)

        # 亮度向增加30%, 饱和度减少25%
        lum_target, lum_percent = 1.0, 0.3
        color_left.lum = color_left.lum * (1 - lum_percent) + lum_target * lum_percent
        color_right.lum = color_right.lum * (1 - lum_percent) + lum_target * lum_percent
        sat_target, sat_percent = 0.0, 0.25
        color_left.sat = color_left.sat * (1 - sat_percent) + sat_target * sat_percent
        color_right.sat = color_right.sat * (1 - sat_percent) + sat_target * sat_percent

        self.bg_binder.set_color(color_left.wxcolor, color_right.wxcolor)
        self.Refresh()

    def load_head(self):
        head = skin_mgr.get_player_head(HeadLoadData(Player(self.player), 120))[1]
        self.head.SetBitmap(PilImg2WxImg(head))
        self.set_icon(PilImg2WxImg(head))
        self.load_card_color(head)
        self.Layout()
