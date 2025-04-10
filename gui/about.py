import os

import wx
from wx import adv

from gui.widget import ft
from lib.info import version


class AboutPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 添加项目图标（新增代码）
        icon_path = os.path.join("assets", "icon", "icon128px.png")
        bitmap = wx.StaticBitmap(self, bitmap=wx.Bitmap(icon_path))
        main_sizer.Add(bitmap, 0, wx.CENTER | wx.ALL, 10)

        # 版本信息（原有代码调整）
        self.version_label = wx.StaticText(self, label=f"CloudStatus\nVersion {version}")
        self.version_label.SetFont(ft(36))
        main_sizer.Add(self.version_label, 0, wx.ALL | wx.CENTER, 10)

        # 贡献者信息
        author_label = wx.StaticText(self, label="贡献者: hite4044、Zephyr177")
        author_label.SetFont(ft(18))
        main_sizer.Add(author_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # 许可证信息
        license_label = wx.StaticText(self, label="许可证: MPL-2.0")
        license_label.SetFont(ft(18))
        main_sizer.Add(license_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # GitHub链接
        github_link = adv.HyperlinkCtrl(self, label="GitHub项目地址", url="https://github.com/hite4044/CloudStatus")
        github_link.SetFont(ft(18))
        main_sizer.Add(github_link, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # 项目描述
        description = wx.StaticText(self, label="服务器监测工具, 支持玩家游玩时间分析与数据可视化")
        description.SetFont(ft(16))
        main_sizer.Add(description, 0, wx.ALL, 5)

        self.SetSizer(main_sizer)
