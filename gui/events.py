"""
定义项目事件
"""
from typing import Any

import wx

from lib.data import ServerPoint

csEVT_FILTER_CHANGE = wx.NewEventType()
EVT_FILTER_CHANGE = wx.PyEventBinder(csEVT_FILTER_CHANGE)
csEVT_GET_STATUS_NOW = wx.NewEventType()
EVT_GET_STATUS_NOW = wx.PyEventBinder(csEVT_GET_STATUS_NOW)
csEVT_PLAYER_ONLINE_INFO = wx.NewEventType()
EVT_PLAYER_ONLINE_INFO = wx.PyEventBinder(csEVT_PLAYER_ONLINE_INFO)
csEVT_PAUSE_STATUS = wx.NewEventType()
EVT_PAUSE_STATUS = wx.PyEventBinder(csEVT_PAUSE_STATUS)
csEVT_SET_AS_OVERVIEW = wx.NewEventType()
EVT_SET_AS_OVERVIEW = wx.PyEventBinder(csEVT_SET_AS_OVERVIEW)
csEVT_ADD_PLAYER_OVERVIEW = wx.NewEventType()
EVT_ADD_PLAYER_OVERVIEW = wx.PyEventBinder(csEVT_ADD_PLAYER_OVERVIEW)


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


class PauseStatusEvent(wx.PyCommandEvent):
    def __init__(self, pause_status: bool):
        wx.PyCommandEvent.__init__(self, csEVT_PAUSE_STATUS, wx.ID_ANY)
        self.pause_status = pause_status


class SetAsOverviewEvent(wx.PyCommandEvent):
    def __init__(self, point: ServerPoint):
        wx.PyCommandEvent.__init__(self, csEVT_SET_AS_OVERVIEW, wx.ID_ANY)
        self.point = point

class AddPlayerOverviewEvent(wx.PyCommandEvent):
    def __init__(self, player: str):
        wx.PyCommandEvent.__init__(self, csEVT_ADD_PLAYER_OVERVIEW, wx.ID_ANY)
        self.player = player