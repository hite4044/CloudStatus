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
csEVT_ADD_PLAYERS_OVERVIEW = wx.NewEventType()
EVT_ADD_PLAYERS_OVERVIEW = wx.PyEventBinder(csEVT_ADD_PLAYERS_OVERVIEW)
csEVT_APPLY_VALUE = wx.NewEventType()
EVT_APPLY_VALUE = wx.PyEventBinder(csEVT_APPLY_VALUE)
csEVT_ASK_TO_ADD_PLAYER = wx.NewEventType()
EVT_ASK_TO_ADD_PLAYER = wx.PyEventBinder(csEVT_ASK_TO_ADD_PLAYER)
csREMOVE_PLAYER_OVERVIEW = wx.NewEventType()
EVT_REMOVE_PLAYER_OVERVIEW = wx.PyEventBinder(csREMOVE_PLAYER_OVERVIEW)


class RemovePlayerOverviewEvent(wx.PyCommandEvent):
    def __init__(self, player: str):
        wx.PyCommandEvent.__init__(self, csREMOVE_PLAYER_OVERVIEW, wx.ID_ANY)
        self.player = player


class AskToAddPlayerEvent(wx.PyCommandEvent):
    def __init__(self):
        wx.PyCommandEvent.__init__(self, csEVT_ASK_TO_ADD_PLAYER, wx.ID_ANY)


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


class AddPlayersOverviewEvent(wx.PyCommandEvent):
    def __init__(self, players: list[str]):
        wx.PyCommandEvent.__init__(self, csEVT_ADD_PLAYERS_OVERVIEW, wx.ID_ANY)
        self.players = players


class ApplyValueEvent(wx.PyCommandEvent):
    def __init__(self):
        wx.PyCommandEvent.__init__(self, csEVT_APPLY_VALUE, wx.ID_ANY)
