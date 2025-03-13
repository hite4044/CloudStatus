"""
管理配置的文件
"""
import json
from enum import Enum
from os.path import exists
from typing import Any, Callable

from lib.log import logger


class DataSaveFmt(Enum):
    NORMAL = 0
    PLAYER_MAPPING = 1


class Configer:
    """配置文件管理器"""
    addr: str = "127.0.0.1:25565"
    server_name: str = "MC服务器"
    check_inv: int = 60.0
    points_per_file: int = 1200
    saved_per_points: int = 10
    fix_sep: float = 300.0
    min_online_time: int = 60
    data_load_threads: int = 8
    data_dir: str = "./data"
    enable_data_save: bool = True
    use_little_skin: bool = False
    data_save_fmt: DataSaveFmt = DataSaveFmt.NORMAL

    def __init__(self):
        self.config_vars = {}
        # 查找类下所有配置项
        for key in dir(self):
            value = getattr(self, key)
            if not key.startswith("_") and not key.startswith("config_vars") and not isinstance(value, Callable):
                self.config_vars[key] = value
        self.load()

    def load(self):
        """加载配置文件"""
        if not exists("./config.json"):
            self.save()
        else:
            logger.info("读取配置文件...")
            with open("./config.json", "r", encoding="utf-8") as f:
                cfg_dict: dict = json.load(f)
                for key, value in cfg_dict.items():
                    now_value = getattr(self, key) if hasattr(self, key) else None
                    if isinstance(now_value, Enum):
                        value = now_value.__class__(value)
                    self.config_vars[key] = value
                    setattr(self, key, value)

    def save(self):
        """保存配置文件"""
        logger.info("保存配置文件...")
        config_vars_org = {}
        for key, value in self.config_vars.items():
            if isinstance(value, Enum):
                config_vars_org[key] = value.value
            else:
                config_vars_org[key] = value
        with open("./config.json", "w") as f:
            f.write(json.dumps(self.config_vars, indent=4))

    def set_value(self, key: str, value: Any):
        """设置配置项的值"""
        self.config_vars[key] = value
        setattr(self, key, value)


config = Configer()
