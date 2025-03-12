from threading import Thread

from gui.widget import *
from lib.common_data import common_data


class PlayerDayOnlinePlot(wx.Window):
    """玩家逐小时在线图表"""

    def __init__(self, parent: wx.Window, player: str):
        super().__init__(parent, id=wx.ID_ANY, pos=wx.DefaultPosition, style=wx.TRANSPARENT_WINDOW,
                         name='PlayerDayOnlinePlot')
        self.player = player
        self.datas: list[float] = [0.1, 0.4, 0.9, 1.0, 0.1, 0.6]
        Thread(target=self.load_hour_online_data, args=(player,)).start()
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
            dc.DrawRectangle(int(width * i / len(self.datas)), int(height * (1 - self.datas[i])),
                             int(width / len(self.datas)), int(height * self.datas[i]))


class PlayerOnlineWin(wx.Frame):
    """
    一个查看玩家逐小时在线几率的窗口
    """

    def __init__(self, parent: wx.Window, player: str):
        wx.Frame.__init__(self, parent, title=player + " 逐小时在线分析", size=(400, 300))
        self.SetFont(parent.GetFont())
        self.player = player
        self.head = CenteredBitmap(self)
        self.name_label = TransparentCenteredText(self, label=player, size=(-1, 32))
        self.plot = PlayerDayOnlinePlot(self, player)
        self.set_best_font_size()
        self.bg_binder = GradientBgBinder(self)
        self.bg_binder.set_color(self.GetBackgroundColour())
        Thread(target=load_player_head, args=(player, self.load_head, 80)).start()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.head, 0, wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT, 5)
        sizer.Add(self.name_label, 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(self.plot, 1, wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, 5)
        self.SetSizer(sizer)

    def set_best_font_size(self):
        dc = wx.ClientDC(self.name_label)
        ft_size = 18
        while True:
            dc.SetFont(ft(ft_size))
            size = dc.GetTextExtent(self.name_label.GetLabel())
            if size[0] > 180:
                ft_size -= 1
            else:
                break
        self.name_label.SetFont(ft(ft_size))

    def set_icon(self):
        icon = wx.Icon(f"heads_cache/{self.player}_80.png", wx.BITMAP_TYPE_PNG)
        self.SetIcon(icon)

    def load_card_color(self):
        """从玩家头像中提取两个眼睛的颜色并应用到控件中"""
        image = Image.open(f"heads_cache/{self.player}_80.png")
        left_eye = image.getpixel((28, 58))[:3]
        right_eye = image.getpixel((58, 58))[:3]

        if left_eye == right_eye:
            color_left = color_right = EasyColor(*right_eye)
        else:
            color_left, color_right = EasyColor(*left_eye), EasyColor(*right_eye)
        self.bg_binder.set_color(color_left.set_luminance(0.5).wxcolor, color_right.set_luminance(0.7).wxcolor)
        self.Refresh()

    def load_head(self, head: wx.Bitmap):
        self.set_icon()
        self.head.SetBitmap(head)
        self.load_card_color()
        self.Layout()
