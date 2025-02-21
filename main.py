from lib.log import logger

if __name__ == "__main__":
    logger.info("加载依赖库中...")
    import wx
    from gui.main_win import GUI

    app = wx.App()
    gui = GUI()
    logger.info("布局窗口")
    gui.Show()
    logger.info("加载完成！")
    try:
        app.MainLoop()
    except KeyboardInterrupt:
        pass
