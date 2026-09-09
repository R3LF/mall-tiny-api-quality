"""公共工具：YAML 读取 + 测试数据命名。

路径锚定在本文件所在位置向上推到项目根，因此无论从哪个目录
运行 pytest，data/、config/ 的相对路径都不会失效。
"""
import random
import time
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_yaml(rel_path: str):
    """读取项目根下相对路径的 YAML 文件，解析为 Python 对象。

    参数示例：load_yaml("data/login_cases.yaml")
    """
    with open(PROJECT_ROOT / rel_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def unique_name(prefix: str) -> str:
    """生成 qa_ 体系下的唯一名称（前缀_月日时分秒_随机三位）。

    凡是"创建数据"的用例都必须用它命名：固定名字二次运行会撞
    重复冲突（如注册 code 500），且残留数据会让测试不可重复。
    """
    return f"{prefix}_{time.strftime('%m%d%H%M%S')}_{random.randint(100, 999)}"
