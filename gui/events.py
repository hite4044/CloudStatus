"""
定义项目事件
"""
import wx
from typing import Any

csEVT_FILTER_CHANGE = wx.NewEventType()
EVT_FILTER_CHANGE = wx.PyEventBinder(csEVT_FILTER_CHANGE)
csEVT_GET_STATUS_NOW = wx.NewEventType()
EVT_GET_STATUS_NOW = wx.PyEventBinder(csEVT_GET_STATUS_NOW)
csEVT_PLAYER_ONLINE_INFO = wx.NewEventType()
EVT_PLAYER_ONLINE_INFO = wx.PyEventBinder(csEVT_PLAYER_ONLINE_INFO)


class FilterChangeEvent(wx.PyCommandEvent):
    def __init__(self, filter_: Any):
        wx.PyCommandEvent.__init__(self, csEVT_FILTER_CHANGE, wx.ID_ANY)
        self.filter = filter_


class GetStatusNowEvent(wx.PyCommandEvent):
    def __init__(self):
        wx.PyCommandEvent.__init__(self, csEVT_GET_STATUS_NOW, wx.ID_ANY)


class PlayerOnlineInfoEvent(wx.PyCommandEvent):
    def __init__(self, players_info: dict[str, list[tuple[float, float]]]):
        wx.PyCommandEvent.__init__(self, csEVT_PLAYER_ONLINE_INFO, wx.ID_ANY)
        self.players_info = players_info
