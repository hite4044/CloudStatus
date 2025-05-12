# noinspection PyUnresolvedReferences
from dataclasses import dataclass, field
from io import BytesIO
from typing import cast

import colorthief

from gui.widget import *
from lib.config import config, PlayerColorPickWay
from lib.log import logger


@dataclass
class EyeResampleRule:
    eye_pos: tuple[int, int]
    resample_points: list[tuple[int, int]]
    res_resample_points: list[tuple[int, int]] = field(default_factory=list)


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


def get_player_color(head: Image.Image, way: PlayerColorPickWay):
    if way == PlayerColorPickWay.EYE_COLOR:
        return get_eye_color(head)
    elif way == PlayerColorPickWay.FIXED_EYE_POS:
        if not (0 <= config.eye_fixed_pos_x < 8 and 0 <= config.eye_fixed_pos_y < 8):
            logger.error("固定眼睛位置超出范围")
            return (0, 0, 0), (0, 0, 0)
        pt_size = head.height / 8

        def get_pixel(x_pos: int, y_pos: int):
            return head.getpixel((int(x_pos * pt_size + pt_size / 2), int(y_pos * pt_size + pt_size / 2)))[:3]

        return (get_pixel(config.eye_fixed_pos_x, config.eye_fixed_pos_y),
                get_pixel(8 - config.eye_fixed_pos_x, config.eye_fixed_pos_y))
    image_io = BytesIO()
    head.save(image_io, format="PNG")
    image_io.seek(0)
    thief = colorthief.ColorThief(image_io)
    color_list = thief.get_palette(color_count=config.color_extract_num, quality=config.color_extract_quality)
    try:
        if way == PlayerColorPickWay.MAIN_COLOR:
            return color_list[0], color_list[0]
        elif way == PlayerColorPickWay.SECOND_COLOR:
            return color_list[1], color_list[1]
        elif way == PlayerColorPickWay.CUSTOM_COLOR_INDEX:
            return color_list[config.extracted_color_index], color_list[config.extracted_color_index2]
    except IndexError:
        logger.error("颜色索引超出范围")
        return (0, 0, 0), (0, 0, 0)
    logger.error("未知的颜色提取方式")
    return (0, 0, 0), (0, 0, 0)
