import wx

from gui.widget import ft
from lib.info import version


class AboutPanel(wx.Panel):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.version_label = wx.StaticText(self, label=f"CloudStatus\nVersion {version}")
        self.version_label.SetFont(ft(36))
